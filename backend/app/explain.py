from __future__ import annotations

from app.models import PersonBreakdown, SplitResponse


def build_explanations(result: SplitResponse) -> list[dict[str, str]]:
    """Human-readable 'why you owe X' — standout for product review."""
    out: list[dict[str, str]] = []
    for person in result.per_person:
        parts = [
            f"Food share: ₹{person.subtotal}",
        ]
        if person.service_share:
            parts.append(f"Service: ₹{person.service_share}")
        if person.tax_share:
            parts.append(f"Tax (GST): ₹{person.tax_share}")
        if person.discount_share:
            parts.append(f"Discount: ₹{person.discount_share}")
        items = ", ".join(person.items[:4])
        if len(person.items) > 4:
            items += f" (+{len(person.items) - 4} more)"
        summary = " + ".join(parts) + f" = ₹{person.total}"
        out.append(
            {
                "name": person.name,
                "summary": summary,
                "items": items or "—",
            }
        )
    return out


def build_share_message(result: SplitResponse) -> str:
    """WhatsApp-ready settle-up text — practical standout feature."""
    lines = [f"🧾 Fair Split — Grand total ₹{result.grand_total:,}"]
    if result.paid_by:
        lines.append(f"Paid by: {result.paid_by}")
    lines.append("")
    for person in result.per_person:
        lines.append(f"• {person.name}: ₹{person.total:,}")
    if result.settle_up:
        lines.append("")
        lines.append("Settle up:")
        for entry in result.settle_up:
            lines.append(f"  {entry.from_} → {entry.to}: ₹{entry.amount:,}")
    if result.flags:
        lines.append("")
        lines.append(f"⚠️ Note: {result.flags[0]}")
    return "\n".join(lines)
