from __future__ import annotations

from dataclasses import dataclass

from app.bill_health import compute_bill_health
from app.calculator import compute_split
from app.explain import build_explanations, build_share_message
from app.llm import BillExtraction, process_bill
from app.models import SplitResponse


@dataclass
class SplitResult:
    """Assignment-compliant core + optional enrichments for UI/submission."""
    split: SplitResponse
    bill_health: dict
    explanations: list[dict[str, str]]
    share_message: str
    model_used: str | None


def run_split(
    image_bytes: bytes,
    description: str,
    mime_type: str = "image/jpeg",
) -> SplitResult:
    extracted: BillExtraction = process_bill(image_bytes, description.strip(), mime_type)
    split = compute_split(
        extracted.receipt,
        extracted.description,
        extra_assumptions=extracted.assumptions,
        extra_flags=extracted.flags,
    )
    return SplitResult(
        split=split,
        bill_health=compute_bill_health(extracted.receipt, split),
        explanations=build_explanations(split),
        share_message=build_share_message(split),
        model_used=extracted.model_used,
    )
