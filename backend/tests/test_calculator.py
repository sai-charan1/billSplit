import pytest

from app.calculator import compute_split
from app.models import DescriptionData, ItemAssignment, ReceiptData, ReceiptLineItem


def _r2_receipt() -> tuple[ReceiptData, DescriptionData]:
    receipt = ReceiptData(
        items=[
            ReceiptLineItem(name="Paneer Butter Masala", qty=1, amount=320),
            ReceiptLineItem(name="Dal Makhani", qty=1, amount=260),
            ReceiptLineItem(name="Butter Naan", qty=4, amount=240),
            ReceiptLineItem(name="Jeera Rice", qty=1, amount=180),
            ReceiptLineItem(name="Gulab Jamun", qty=2, amount=120),
            ReceiptLineItem(name="Masala Papad", qty=2, amount=100),
        ],
        subtotal=1220,
        service_charge=61,
        gst=64.05,
        round_off=-0.05,
        grand_total=1345,
    )
    description = DescriptionData(
        people=["Aman", "Priya", "Karan", "Sara"],
        paid_by="Priya",
        assignments=[
            ItemAssignment(item_ref="Gulab Jamun", consumers=["Priya", "Karan"]),
            ItemAssignment(item_ref="everything else", consumers=["Aman", "Priya", "Karan", "Sara"]),
        ],
    )
    return receipt, description


def _r4_receipt() -> tuple[ReceiptData, DescriptionData]:
    receipt = ReceiptData(
        items=[
            ReceiptLineItem(name="Chicken Biryani", qty=2, amount=560),
            ReceiptLineItem(name="Veg Biryani", qty=1, amount=240),
            ReceiptLineItem(name="Mutton Rogan Josh", qty=1, amount=420),
            ReceiptLineItem(name="Raita", qty=2, amount=120),
            ReceiptLineItem(name="Soft Drinks", qty=3, amount=180),
        ],
        subtotal=1520,
        service_charge=76,
        gst=68.4,
        discount=-228,
        round_off=-0.4,
        grand_total=1436,
    )
    description = DescriptionData(
        people=["Dev", "Nikhil", "Anjali", "Farah"],
        paid_by="Anjali",
        assignments=[
            ItemAssignment(item_ref="Chicken Biryani", consumers=["Dev", "Nikhil"]),
            ItemAssignment(item_ref="Veg Biryani", consumers=["Anjali"]),
            ItemAssignment(item_ref="Mutton Rogan Josh", consumers=["Farah"]),
            ItemAssignment(item_ref="Raita", consumers=["Dev", "Nikhil", "Anjali", "Farah"]),
            ItemAssignment(item_ref="Soft Drinks", consumers=["Dev", "Nikhil", "Anjali", "Farah"]),
        ],
    )
    return receipt, description


@pytest.mark.parametrize("builder", [_r2_receipt, _r4_receipt])
def test_sample_reconciles(builder) -> None:
    receipt, description = builder()
    result = compute_split(receipt, description)

    assert result.grand_total == int(receipt.grand_total)
    assert result.reconciliation.sum_of_person_totals == result.grand_total
    assert result.reconciliation.matches_bill is True
    assert result.paid_by == description.paid_by
    assert len(result.per_person) == len(description.people)


def test_r2_gulab_jamun_split() -> None:
    receipt, description = _r2_receipt()
    result = compute_split(receipt, description)

    by_name = {p.name: p for p in result.per_person}
    assert by_name["Priya"].subtotal > by_name["Aman"].subtotal
    assert by_name["Karan"].subtotal > by_name["Aman"].subtotal
    assert by_name["Aman"].subtotal == by_name["Sara"].subtotal


def test_no_payer_flags_and_empty_settle_up() -> None:
    receipt = ReceiptData(
        items=[ReceiptLineItem(name="Tea", qty=1, amount=100)],
        subtotal=100,
        service_charge=5,
        gst=5,
        grand_total=110,
    )
    description = DescriptionData(
        people=["A", "B"],
        paid_by=None,
        assignments=[ItemAssignment(item_ref="Tea", consumers=["A", "B"])],
    )
    result = compute_split(receipt, description)
    assert result.paid_by is None
    assert result.settle_up == []
    assert any("No payer" in flag for flag in result.flags)


def test_item_not_on_bill_is_flagged() -> None:
    receipt = ReceiptData(
        items=[ReceiptLineItem(name="Tea", qty=1, amount=100)],
        subtotal=100,
        service_charge=5,
        gst=5,
        grand_total=110,
    )
    description = DescriptionData(
        people=["A"],
        paid_by="A",
        assignments=[ItemAssignment(item_ref="Sushi", consumers=["A"])],
    )
    result = compute_split(receipt, description)
    assert any("not found on receipt" in flag for flag in result.flags)


def test_discount_allocated_proportionally() -> None:
    receipt, description = _r4_receipt()
    result = compute_split(receipt, description)
    assert all(p.discount_share <= 0 for p in result.per_person)
    assert sum(p.discount_share for p in result.per_person) <= 0
