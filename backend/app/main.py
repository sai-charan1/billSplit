from __future__ import annotations

import base64
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import load_env
from app.gemini_client import QuotaExhaustedError, is_valid_key_format, model_fallback_chain
from app.groq_client import GroqError, GroqQuotaError, is_groq_configured
from app.models import (
    BillHealth,
    BillHealthCheck,
    PersonExplanation,
    SplitEnrichedResponse,
    SplitRequest,
    SplitResponse,
)
from app.pipeline import run_split

load_env()

app = FastAPI(
    title="Fair Split API",
    description="Split restaurant bills fairly from a receipt photo and plain-English description.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _decode_image(receipt_base64: str) -> tuple[bytes, str]:
    raw = receipt_base64.strip()
    if raw.startswith("data:"):
        match = re.match(r"data:(image/[\w+.-]+);base64,(.+)", raw, re.DOTALL)
        if match:
            return base64.b64decode(match.group(2)), match.group(1)
    return base64.b64decode(raw), "image/jpeg"


def _http_error_from_llm(exc: Exception) -> HTTPException:
    if isinstance(exc, (QuotaExhaustedError, GroqQuotaError)):
        return HTTPException(status_code=429, detail=str(exc))
    if isinstance(exc, (RuntimeError, GroqError)):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


def _to_enriched(result) -> SplitEnrichedResponse:
    return SplitEnrichedResponse(
        per_person=result.split.per_person,
        grand_total=result.split.grand_total,
        reconciliation=result.split.reconciliation,
        paid_by=result.split.paid_by,
        settle_up=result.split.settle_up,
        assumptions=result.split.assumptions,
        flags=result.split.flags,
        bill_health=BillHealth(
            score=result.bill_health["score"],
            grade=result.bill_health["grade"],
            checks=[BillHealthCheck(**c) for c in result.bill_health["checks"]],
        ),
        explanations=[PersonExplanation(**e) for e in result.explanations],
        share_message=result.share_message,
        model_used=result.model_used,
    )


@app.on_event("startup")
def on_startup() -> None:
    load_env()
    providers = os.getenv("LLM_PROVIDER_CHAIN", "groq,gemini,rules")
    print(f"Fair Split v2 | LLM chain: {providers}")
    if is_groq_configured():
        print("GROQ_API_KEY loaded (primary)")
    else:
        print("WARNING: GROQ_API_KEY not set — https://console.groq.com/keys")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if key and key != "your_gemini_api_key_here":
        print(f"GEMINI_API_KEY loaded | models: {', '.join(model_fallback_chain())}")


@app.get("/health")
def health() -> dict:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return {
        "status": "ok",
        "version": "2.0.0",
        "groq_configured": is_groq_configured(),
        "gemini_configured": bool(key) and key != "your_gemini_api_key_here",
        "gemini_key_format_valid": is_valid_key_format(key),
        "provider_chain": os.getenv("LLM_PROVIDER_CHAIN", "groq,gemini,rules").split(","),
        "gemini_model_chain": model_fallback_chain(),
        "features": [
            "multi_provider_llm",
            "receipt_normalization",
            "rule_based_fallback",
            "bill_health_score",
            "share_message",
            "per_person_explanations",
        ],
    }


@app.post("/split", response_model=SplitResponse)
def split_bill(request: SplitRequest) -> SplitResponse:
    """Assignment contract — exact response shape."""
    return _split_core(request)


@app.post("/split/enriched", response_model=SplitEnrichedResponse)
def split_bill_enriched(request: SplitRequest) -> SplitEnrichedResponse:
    """Same split + bill health, explanations, WhatsApp share text (for UI/demo)."""
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="description is required")
    if not request.receipt_base64.strip():
        raise HTTPException(status_code=400, detail="receipt_base64 is required")

    try:
        image_bytes, mime_type = _decode_image(request.receipt_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {exc}") from exc

    try:
        result = run_split(image_bytes, request.description.strip(), mime_type)
    except (QuotaExhaustedError, GroqQuotaError, GroqError, RuntimeError) as exc:
        raise _http_error_from_llm(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Bill processing failed: {exc}") from exc

    return _to_enriched(result)


def _split_core(request: SplitRequest) -> SplitResponse:
    enriched = split_bill_enriched(request)
    return SplitResponse(
        per_person=enriched.per_person,
        grand_total=enriched.grand_total,
        reconciliation=enriched.reconciliation,
        paid_by=enriched.paid_by,
        settle_up=enriched.settle_up,
        assumptions=enriched.assumptions,
        flags=enriched.flags,
    )


