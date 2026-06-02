from app.description_rules import parse_description_rules
from app.models import ReceiptLineItem


def test_rule_parser_shared_subset_description() -> None:
    description = (
        "Four of us: Aman, Priya, Karan, Sara. "
        "The Gulab Jamun was shared just by Priya and Karan. "
        "Everything else was common to all four. Priya paid."
    )
    items = [
        ReceiptLineItem(name="Paneer Butter Masala", qty=1, amount=320),
        ReceiptLineItem(name="Dal Makhani", qty=1, amount=260),
        ReceiptLineItem(name="Gulab Jamun", qty=2, amount=120),
    ]
    result = parse_description_rules(description, items)
    assert "Priya" in result.people
    assert "Aman" in result.people
    assert result.paid_by == "Priya"
    assert any(a.item_ref.lower().find("gulab") >= 0 or "Gulab" in a.item_ref for a in result.assignments)
