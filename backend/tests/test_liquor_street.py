from app.calculator import compute_split
from app.description_rules import parse_description_rules
from app.models import ReceiptData, ReceiptLineItem
from app.receipt_normalize import normalize_receipt


def _liquor_street_receipt() -> ReceiptData:
    receipt = ReceiptData(
        restaurant="Liquor Street",
        items=[
            ReceiptLineItem(name="Tandoori chicken", qty=1, amount=309.75),
            ReceiptLineItem(name="Lasooni Dal Tadka", qty=1, amount=288.75),
            ReceiptLineItem(name="HYDERABADI MURG BIRYANI", qty=1, amount=393.75),
            ReceiptLineItem(name="Tandoori Roti all food less spicy", qty=2, amount=63.0),
            ReceiptLineItem(name="Tandoori Roti", qty=1, amount=31.50),
        ],
        subtotal=1035,
        service_charge=0,
        gst=51.78,
        grand_total=1139,
    )
    receipt, _ = normalize_receipt(receipt)
    return receipt


DESCRIPTION = (
    "3 of us went sai charan lohitha - all of us ate all split all into 3 "
    "sai paid the bill"
)


def test_liquor_street_normalize() -> None:
    receipt = _liquor_street_receipt()
    line_sum = sum(i.amount for i in receipt.items)
    assert abs(line_sum - 1035) <= 1
    assert receipt.service_charge > 0


def test_liquor_street_equal_split() -> None:
    receipt = _liquor_street_receipt()
    desc = parse_description_rules(DESCRIPTION, receipt.items)
    assert desc.people == ["Sai", "Charan", "Lohitha"]
    assert desc.paid_by == "Sai"
    assert any(a.item_ref == "everything else" for a in desc.assignments)

    result = compute_split(receipt, desc)
    assert result.grand_total == 1139
    assert result.reconciliation.matches_bill is True
    assert all(p.total > 0 for p in result.per_person)
    assert all(p.service_share > 0 for p in result.per_person)

    items_joined = " ".join(result.per_person[0].items)
    assert "Tandoori chicken" in items_joined or "everything" in str(result.per_person[0].items).lower()
