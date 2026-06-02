from __future__ import annotations

import re

from app.models import DescriptionData, ItemAssignment, ReceiptLineItem


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:].lower()


def _split_names(raw: str) -> list[str]:
    parts = re.split(r",|\band\b|;", raw, flags=re.IGNORECASE)
    return [_normalize_name(p.strip().strip(".")) for p in parts if p.strip()]


def _split_space_names(raw: str) -> list[str]:
    parts = re.split(r"[\s,]+", raw.strip())
    return [_normalize_name(p) for p in parts if p.strip()]


def _extract_people(text: str) -> list[str]:
    patterns = [
        r"(?:one|two|three|four|five|six|\d+)\s+of\s+us\s+went\s+([a-z ,]+)",
        r"(?:one|two|three|four|five|six|\d+)\s+of\s+us\s*[—\-:\s]+([^.]+)",
        r"(?:one|two|three|four|five|six|\d+)\s+of\s+us\s+([^.]+)",
        r"^([A-Za-z]+(?:,\s*[A-Za-z]+){1,})",
    ]
    for i, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            raw = match.group(1).split("-")[0]
            names = _split_space_names(raw) if i == 0 else _split_names(raw)
            if len(names) >= 2:
                return names
    return []


def _extract_payer(text: str) -> str | None:
    match = re.search(r"([A-Za-z]+)\s+paid\.?\s*$", text.strip(), re.IGNORECASE)
    if match:
        return _normalize_name(match.group(1))
    match = re.search(r"([A-Za-z]+)\s+paid\b", text, re.IGNORECASE)
    return _normalize_name(match.group(1)) if match else None


def _find_item_ref(phrase: str, items: list[ReceiptLineItem]) -> str:
    phrase_lower = phrase.lower().strip()
    for item in items:
        if phrase_lower in item.name.lower() or item.name.lower() in phrase_lower:
            return item.name
    return phrase.strip()


def _extract_assignments(text: str, people: list[str], items: list[ReceiptLineItem]) -> list[ItemAssignment]:
    assignments: list[ItemAssignment] = []
    lower = text.lower()

    # "all of us ate all" / "split all into 3" — full equal split (no per-item rules)
    if re.search(r"all of us ate all|split all (?:into|equally|between)|split equally", lower):
        if not re.search(r"except|shared (?:just )?by|each had|\bate \d+", lower):
            assignments.append(ItemAssignment(item_ref="everything else", consumers=people))
            return assignments

    # "sai and charan ate 2 veg biryanis each"
    for match in re.finditer(
        r"([a-z]+(?:\s+and\s+[a-z]+)+)\s+ate\s+(\d+)\s+([^.]+?)\s+each",
        lower,
    ):
        consumers = [_normalize_name(n) for n in re.split(r"\s+and\s+", match.group(1))]
        qty = float(match.group(2))
        item_ref = _find_item_ref(match.group(3).strip(), items)
        assignments.append(
            ItemAssignment(item_ref=item_ref, consumers=consumers, quantity_per_consumer=qty)
        )

    other_biryani = re.search(r"all other(?:s)?\s+ate\s+(\d+)(?:\s+([^.]+))?", lower)
    if other_biryani:
        qty = float(other_biryani.group(1))
        item_phrase = other_biryani.group(2) or "veg biryani"
        if "biryani" not in item_phrase and "veg biryani" in lower:
            item_phrase = "veg biryani"
        item_ref = _find_item_ref(item_phrase.strip(), items)
        named = set()
        for a in assignments:
            named.update(a.consumers)
        others = [p for p in people if p not in named]
        if others:
            assignments.append(
                ItemAssignment(item_ref=item_ref, consumers=others, quantity_per_consumer=qty)
            )

    for match in re.finditer(
        r"all except ([a-z]+)\s+ate\s+([a-z]+(?:\s+[a-z]+){0,2})(?=\s*(?:\.|,|\band\b|$))",
        lower,
    ):
        excluded = _normalize_name(match.group(1))
        item_ref = _find_item_ref(match.group(2).strip(), items)
        consumers = [p for p in people if p != excluded]
        assignments.append(ItemAssignment(item_ref=item_ref, consumers=consumers, quantity_per_consumer=1.0))

    for match in re.finditer(
        r"(?:\band\s+)?([a-z]+)\s+ate\s+([a-z]+(?:\s+[a-z]+){0,2})\s*$",
        lower.strip(),
    ):
        person = _normalize_name(match.group(1))
        item_phrase = match.group(2).strip()
        if person not in people:
            continue
        item_ref = _find_item_ref(item_phrase, items)
        assignments.append(
            ItemAssignment(item_ref=item_ref, consumers=[person], quantity_per_consumer=1.0)
        )

    for match in re.finditer(
        r"([^.]+?)\s+(?:was|were)\s+shared(?:\s+just)?\s+by\s+([^.]+?)(?:\.|,|$)",
        text,
        re.IGNORECASE,
    ):
        item_ref = _find_item_ref(match.group(1).strip(), items)
        consumers = _split_names(match.group(2))
        assignments.append(ItemAssignment(item_ref=item_ref, consumers=consumers))

    for match in re.finditer(
        r"([A-Za-z]+(?:\s+and\s+[A-Za-z]+)?)\s+each\s+had\s+(?:a\s+|the\s+)?([^.]+?)(?:\.|,|$)",
        text,
        re.IGNORECASE,
    ):
        consumers = _split_names(match.group(1))
        item_ref = _find_item_ref(match.group(2).strip(), items)
        assignments.append(ItemAssignment(item_ref=item_ref, consumers=consumers))

    if any(p in lower for p in ("everything else", "common to all", "rest of us", "the rest")):
        assignments.append(ItemAssignment(item_ref="everything else", consumers=people))

    return assignments


def parse_description_rules(description: str, items: list[ReceiptLineItem]) -> DescriptionData:
    people = _extract_people(description)
    paid_by = _extract_payer(description)
    assignments = _extract_assignments(description, people, items)
    assumptions: list[str] = ["Rule-based description parser used (no LLM available)"]
    flags: list[str] = []

    if not people:
        flags.append("Could not identify diners from description — rule parser")
    if not paid_by:
        flags.append("No payer stated in description")
    if not assignments:
        flags.append("No item assignments detected — all items will be split equally")

    return DescriptionData(
        people=people,
        paid_by=paid_by,
        assignments=assignments,
        assumptions=assumptions,
        flags=flags,
    )
