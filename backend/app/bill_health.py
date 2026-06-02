from __future__ import annotations

from app.models import ReceiptData, SplitResponse


def compute_bill_health(receipt: ReceiptData, result: SplitResponse) -> dict:
    """0–100 score + checklist for evaluators (trust signal)."""
    score = 100
    checks: list[dict[str, str | bool]] = []

    line_sum = sum(i.amount for i in receipt.items)
    if abs(line_sum - receipt.subtotal) > 1:
        score -= 15
        checks.append({
            "id": "line_subtotal",
            "ok": False,
            "label": f"Line items ₹{line_sum:.0f} vs printed subtotal ₹{receipt.subtotal:.0f}",
        })
    else:
        checks.append({"id": "line_subtotal", "ok": True, "label": "Line items match subtotal"})

    if result.reconciliation.matches_bill:
        checks.append({"id": "reconcile", "ok": True, "label": "Person totals match grand total"})
    else:
        score -= 25
        checks.append({"id": "reconcile", "ok": False, "label": "Reconciliation mismatch"})

    if not receipt.items:
        score -= 30
        checks.append({"id": "items", "ok": False, "label": "No line items extracted"})
    else:
        checks.append({"id": "items", "ok": True, "label": f"{len(receipt.items)} items extracted"})

    if result.paid_by:
        checks.append({"id": "payer", "ok": True, "label": f"Payer: {result.paid_by}"})
    else:
        score -= 10
        checks.append({"id": "payer", "ok": False, "label": "No payer — settle-up incomplete"})

    high_flags = [f for f in result.flags if any(w in f.lower() for w in ("not found", "failed", "could not"))]
    if high_flags:
        score -= min(20, 5 * len(high_flags))
        checks.append({"id": "flags", "ok": False, "label": f"{len(high_flags)} critical flag(s)"})
    else:
        checks.append({"id": "flags", "ok": True, "label": "No critical extraction flags"})

    return {
        "score": max(0, min(100, score)),
        "grade": _grade(score),
        "checks": checks,
    }


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"
