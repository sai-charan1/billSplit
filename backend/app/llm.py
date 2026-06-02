from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from google.genai import types

from app.description_rules import parse_description_rules
from app.gemini_client import (
    LLMServiceError,
    QuotaExhaustedError,
    generate_json as gemini_generate_json,
    get_client as get_gemini_client,
    is_valid_key_format,
)
from app.groq_client import (
    GroqError,
    GroqQuotaError,
    generate_json_text as groq_text,
    generate_json_vision as groq_vision,
    is_groq_configured,
)
from app.models import DescriptionData, ItemAssignment, ReceiptData, ReceiptLineItem
from app.ocr_local import extract_text_from_image
from app.prompts import COMBINED_PROMPT, DESCRIPTION_PROMPT, OCR_RECEIPT_PROMPT
from app.receipt_normalize import normalize_receipt

_is_valid_key_format = is_valid_key_format


@dataclass
class BillExtraction:
    receipt: ReceiptData
    description: DescriptionData
    assumptions: list[str]
    flags: list[str]
    model_used: str | None = None


def _provider_chain() -> list[str]:
    raw = os.getenv("LLM_PROVIDER_CHAIN", "groq,gemini,rules")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _build_receipt(payload: dict[str, Any], flags: list[str]) -> ReceiptData:
    items = [
        ReceiptLineItem(
            name=str(item.get("name", "")).strip(),
            qty=float(item.get("qty", 1)),
            amount=float(item.get("amount", 0)),
        )
        for item in payload.get("items", [])
        if item.get("name")
    ]

    cgst = float(payload.get("cgst", 0) or 0)
    sgst = float(payload.get("sgst", 0) or 0)
    gst = float(payload.get("gst", 0) or 0)
    if gst <= 0 and (cgst > 0 or sgst > 0):
        gst = cgst + sgst

    service = float(payload.get("service_charge", 0) or payload.get("service_tax", 0) or payload.get("s_tax", 0) or 0)

    receipt = ReceiptData(
        restaurant=payload.get("restaurant"),
        items=items,
        subtotal=float(payload.get("subtotal", 0)),
        service_charge=service,
        service_rate_pct=payload.get("service_rate_pct"),
        gst=gst,
        discount=float(payload.get("discount", 0)),
        discount_label=payload.get("discount_label"),
        round_off=float(payload.get("round_off", 0)),
        grand_total=float(payload.get("grand_total", 0)),
    )

    label = (receipt.discount_label or "").lower()
    if receipt.discount > 0 and any(word in label for word in ("discount", "off", "coupon", "welcome")):
        receipt.discount = -receipt.discount
        flags.append("Corrected discount sign to negative (model returned positive reduction)")

    if not items:
        flags.append("No line items extracted from receipt")

    receipt, norm_assumptions = normalize_receipt(receipt)
    flags.extend(norm_assumptions)

    return receipt


def _build_description(payload: dict[str, Any]) -> DescriptionData:
    assignments = [
        ItemAssignment(
            item_ref=str(a.get("item_ref", "")).strip(),
            consumers=[str(c).strip() for c in a.get("consumers", []) if str(c).strip()],
            fraction=float(a.get("fraction", 1.0)),
            quantity_per_consumer=float(a.get("quantity_per_consumer", a.get("qty_per_person", 1.0))),
            note=a.get("note"),
        )
        for a in payload.get("assignments", [])
        if a.get("item_ref")
    ]
    return DescriptionData(
        people=[str(p).strip() for p in payload.get("people", []) if str(p).strip()],
        paid_by=payload.get("paid_by"),
        assignments=assignments,
        assumptions=[str(x) for x in payload.get("assumptions", [])],
        flags=[str(x) for x in payload.get("flags", [])],
    )


def _merge_assumptions(*groups: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _fill_prompt(template: str, **kwargs: str) -> str:
    """Substitute placeholders without interpreting JSON braces in the template."""
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{key}}}", value)
    return result


def _enhance_description(
    description_text: str,
    parsed: DescriptionData,
    receipt_items: list[ReceiptLineItem],
) -> DescriptionData:
    """Merge rule-based parsing when LLM misses quantity / except / equal-split patterns."""
    rules = parse_description_rules(description_text, receipt_items)
    if not rules.people:
        return parsed

    equal_split = bool(
        re.search(
            r"all of us ate all|split all (?:into|equally)|split equally|common to all",
            description_text,
            re.IGNORECASE,
        )
    )
    use_rules = (
        not parsed.people
        or not parsed.assignments
        or equal_split
        or len(rules.assignments) > len(parsed.assignments)
        or any(a.quantity_per_consumer > 1 for a in rules.assignments)
    )
    if not use_rules:
        return parsed

    assumptions = list(parsed.assumptions) + [
        "Description refined with rule-based parser (equal split / quantity / except patterns)"
    ]
    return DescriptionData(
        people=rules.people,
        paid_by=parsed.paid_by or rules.paid_by,
        assignments=rules.assignments,
        assumptions=assumptions,
        flags=list(parsed.flags) + list(rules.flags),
    )


def _parse_combined_response(
    raw: str, flags: list[str], description_text: str
) -> tuple[ReceiptData, DescriptionData]:
    payload = _parse_json_response(raw)
    receipt_payload = payload.get("receipt", payload)
    description_payload = payload.get("description", {})
    receipt = _build_receipt(receipt_payload, flags)
    description = _enhance_description(
        description_text,
        _build_description(description_payload),
        receipt.items,
    )
    return receipt, description


def _try_groq_combined(
    image_bytes: bytes,
    description_text: str,
    mime_type: str,
    flags: list[str],
) -> BillExtraction:
    prompt = _fill_prompt(COMBINED_PROMPT, description=description_text)
    result = groq_vision(prompt, image_bytes, mime_type)
    receipt, description = _parse_combined_response(result.text, flags, description_text)
    return BillExtraction(
        receipt=receipt,
        description=description,
        assumptions=[f"Processed with Groq {result.model} (vision, single call)"],
        flags=flags + description.flags,
        model_used=f"groq:{result.model}",
    )


def _try_gemini_combined(
    image_bytes: bytes,
    description_text: str,
    mime_type: str,
    flags: list[str],
) -> BillExtraction:
    client = get_gemini_client()
    prompt = _fill_prompt(COMBINED_PROMPT, description=description_text)
    result = gemini_generate_json(
        client,
        [prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
    )
    receipt, description = _parse_combined_response(result.text, flags, description_text)
    return BillExtraction(
        receipt=receipt,
        description=description,
        assumptions=[f"Processed with Gemini {result.model} (single combined call)"],
        flags=flags + description.flags,
        model_used=f"gemini:{result.model}",
    )


def _try_groq_ocr_pipeline(
    image_bytes: bytes,
    description_text: str,
    flags: list[str],
) -> BillExtraction:
    ocr_text = extract_text_from_image(image_bytes)
    if not ocr_text:
        raise GroqError("Local OCR unavailable — install tesseract: brew install tesseract")

    flags.append("Used local Tesseract OCR + Groq text model (no vision API)")
    receipt_result = groq_text(_fill_prompt(OCR_RECEIPT_PROMPT, ocr_text=ocr_text))
    receipt = _build_receipt(_parse_json_response(receipt_result.text), flags)

    desc_result = groq_text(
        _fill_prompt(
            DESCRIPTION_PROMPT,
            description=description_text,
            items_json=json.dumps([i.model_dump() for i in receipt.items], indent=2),
        )
    )
    description = _build_description(_parse_json_response(desc_result.text))
    return BillExtraction(
        receipt=receipt,
        description=description,
        assumptions=[
            f"Receipt OCR via Tesseract; structured by Groq {receipt_result.model}",
            f"Description parsed by Groq {desc_result.model}",
        ],
        flags=flags + description.flags,
        model_used=f"groq-ocr:{receipt_result.model}",
    )


def _parse_description_with_providers(description_text: str, receipt: ReceiptData) -> DescriptionData:
    items_json = json.dumps([item.model_dump() for item in receipt.items], indent=2)
    prompt = _fill_prompt(
        DESCRIPTION_PROMPT,
        description=description_text,
        items_json=items_json,
    )

    for provider in _provider_chain():
        if provider == "groq" and is_groq_configured():
            try:
                result = groq_text(prompt)
                desc = _build_description(_parse_json_response(result.text))
                desc.assumptions.insert(0, f"Description parsed with Groq {result.model}")
                return desc
            except (GroqError, GroqQuotaError):
                continue
        if provider == "gemini":
            try:
                client = get_gemini_client()
                result = gemini_generate_json(client, prompt)
                desc = _build_description(_parse_json_response(result.text))
                desc.assumptions.insert(0, f"Description parsed with Gemini {result.model}")
                return desc
            except (QuotaExhaustedError, LLMServiceError, RuntimeError):
                continue
        if provider == "rules":
            return parse_description_rules(description_text, receipt.items)

    return parse_description_rules(description_text, receipt.items)


def process_bill(
    image_bytes: bytes,
    description_text: str,
    mime_type: str = "image/jpeg",
) -> BillExtraction:
    assumptions: list[str] = []
    flags: list[str] = []
    errors: list[str] = []

    for provider in _provider_chain():
        try:
            if provider == "groq" and is_groq_configured():
                return _try_groq_combined(image_bytes, description_text, mime_type, flags)
            if provider == "gemini":
                return _try_gemini_combined(image_bytes, description_text, mime_type, flags)
            if provider == "rules":
                break
        except (GroqError, GroqQuotaError, QuotaExhaustedError, LLMServiceError) as exc:
            errors.append(f"{provider}: {exc}")
            flags.append(f"{provider} unavailable ({type(exc).__name__})")
            continue

    if is_groq_configured():
        try:
            return _try_groq_ocr_pipeline(image_bytes, description_text, flags)
        except (GroqError, GroqQuotaError) as exc:
            errors.append(f"ocr: {exc}")

    flags.append("All LLM providers failed — used rule-based description parser only")
    ocr_text = extract_text_from_image(image_bytes)
    if ocr_text and is_groq_configured():
        try:
            result = groq_text(_fill_prompt(OCR_RECEIPT_PROMPT, ocr_text=ocr_text))
            receipt = _build_receipt(_parse_json_response(result.text), flags)
            description = parse_description_rules(description_text, receipt.items)
            return BillExtraction(
                receipt=receipt,
                description=description,
                assumptions=_merge_assumptions(
                    ["Groq OCR text structuring after vision failure"],
                    description.assumptions,
                ),
                flags=flags + description.flags,
                model_used="groq-ocr+rules",
            )
        except GroqError:
            pass

    raise RuntimeError(
        "Could not process receipt. Set GROQ_API_KEY (free: https://console.groq.com/keys) "
        "or fix GEMINI_API_KEY quota. Use Demo mode for sample bills. "
        f"Errors: {'; '.join(errors) or 'no providers configured'}"
    )


def parse_description(description: str, receipt: ReceiptData) -> DescriptionData:
    return _parse_description_with_providers(description, receipt)


def extract_receipt(image_bytes: bytes, mime_type: str = "image/jpeg") -> tuple[ReceiptData, list[str]]:
    extracted = process_bill(image_bytes, "Split equally among everyone.", mime_type)
    return extracted.receipt, extracted.flags
