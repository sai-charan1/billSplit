from __future__ import annotations

from app.models import ReceiptData, ReceiptLineItem


def _line_sum(items: list[ReceiptLineItem]) -> float:
    return sum(item.amount for item in items)


def _scale_items(items: list[ReceiptLineItem], factor: float) -> list[ReceiptLineItem]:
    return [
        ReceiptLineItem(name=item.name, qty=item.qty, amount=round(item.amount * factor, 2))
        for item in items
    ]


def normalize_receipt(receipt: ReceiptData) -> tuple[ReceiptData, list[str]]:
    """Fix common OCR/LLM extraction mistakes on Indian restaurant bills."""
    assumptions: list[str] = []
    flags: list[str] = []

    items = list(receipt.items)
    line_sum = _line_sum(items)

    # S.Tax / Service Tax → service_charge
    if receipt.service_charge <= 0 and receipt.subtotal > 0:
        implied = line_sum - receipt.subtotal if receipt.subtotal > 0 else 0
        if implied <= 0 and receipt.grand_total > receipt.subtotal:
            gst_est = receipt.gst if receipt.gst > 0 else 0
            implied = receipt.grand_total - receipt.subtotal - gst_est - receipt.discount - receipt.round_off
        if implied > 0:
            receipt.service_charge = round(implied, 2)
            assumptions.append(f"Inferred service charge ₹{receipt.service_charge:.2f} from bill footer")

    # Line totals include ~5% markup but printed subtotal is pre-service base
    if receipt.subtotal > 0 and line_sum > receipt.subtotal + 1:
        ratio = receipt.subtotal / line_sum
        if 0.90 <= ratio <= 0.99:
            items = _scale_items(items, ratio)
            assumptions.append(
                f"Line items used tax-inclusive totals; scaled down by {ratio:.3f} to match printed subtotal ₹{receipt.subtotal:.0f}"
            )
            line_sum = _line_sum(items)

    # Still off — force scale to printed subtotal
    if receipt.subtotal > 0 and abs(line_sum - receipt.subtotal) > 1 and line_sum > 0:
        factor = receipt.subtotal / line_sum
        if 0.85 <= factor <= 1.15:
            items = _scale_items(items, factor)
            assumptions.append(
                f"Adjusted line item amounts to match printed subtotal (factor {factor:.3f})"
            )
            line_sum = _line_sum(items)

    # Infer GST from CGST+SGST if missing
    if receipt.gst <= 0 and receipt.subtotal > 0 and receipt.grand_total > receipt.subtotal:
        remaining = (
            receipt.grand_total
            - receipt.subtotal
            - receipt.service_charge
            - receipt.discount
            - receipt.round_off
        )
        if 0 < remaining <= receipt.subtotal * 0.15:
            receipt.gst = round(remaining, 2)
            assumptions.append(f"Inferred GST ₹{receipt.gst:.2f} from grand total minus subtotal and service")

    # Infer subtotal from items if missing
    if receipt.subtotal <= 0 and line_sum > 0:
        receipt.subtotal = line_sum
        assumptions.append("Subtotal inferred from sum of line items")

    # Infer grand total
    if receipt.grand_total <= 0:
        receipt.grand_total = round(
            receipt.subtotal + receipt.service_charge + receipt.gst + receipt.discount + receipt.round_off
        )
        assumptions.append("Grand total inferred from bill components")

    receipt.items = items
    return receipt, assumptions + flags
