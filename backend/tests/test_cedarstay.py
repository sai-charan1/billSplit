from app.calculator import compute_split
from app.description_rules import parse_description_rules
from app.models import ReceiptData, ReceiptLineItem


def _cedarstay_receipt() -> ReceiptData:
    return ReceiptData(
        restaurant="Cedarstay Hotels",
        items=[
            ReceiptLineItem(name="Veg Biryani", qty=4, amount=360),
            ReceiptLineItem(name="Veg Biryani", qty=2, amount=678),
            ReceiptLineItem(name="Veg Biryani", qty=2, amount=658),
            ReceiptLineItem(name="Hakka Noodles", qty=2, amount=538),
            ReceiptLineItem(name="Hakka Noodles", qty=3, amount=657),
            ReceiptLineItem(name="Butter Naan", qty=1, amount=699),
        ],
        subtotal=3590,
        service_charge=0,
        gst=179.5,
        grand_total=3770,
    )


DESCRIPTION = (
    "six of us sai,charan,sripada,lohitha,sandhya,satyam - "
    "sai and charan ate 2 veg biryanis each all other ate 1 "
    "all except sripada ate hakka noodles and sripada ate butter naan"
)


def test_cedarstay_rules_parser() -> None:
    receipt = _cedarstay_receipt()
    desc = parse_description_rules(DESCRIPTION, receipt.items)
    assert len(desc.people) == 6
    assert "Sai" in desc.people
    assert "Sripada" in desc.people


def test_cedarstay_split_reconciles() -> None:
    receipt = _cedarstay_receipt()
    desc = parse_description_rules(DESCRIPTION, receipt.items)
    result = compute_split(receipt, desc)

    assert result.grand_total == 3770
    assert result.reconciliation.matches_bill is True
    assert all(p.total > 0 for p in result.per_person)

    by_name = {p.name: p for p in result.per_person}
    assert by_name["Sai"].total > by_name["Lohitha"].total
    assert by_name["Sripada"].total > by_name["Sai"].total
    assert "Butter Naan" in " ".join(by_name["Sripada"].items)


def test_no_negative_totals() -> None:
    receipt = _cedarstay_receipt()
    desc = parse_description_rules(DESCRIPTION, receipt.items)
    result = compute_split(receipt, desc)
    assert all(p.total >= 0 for p in result.per_person)
    assert all(p.tax_share >= 0 for p in result.per_person)
