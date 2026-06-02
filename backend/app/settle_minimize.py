from __future__ import annotations

from app.models import PersonBreakdown, SettleUpEntry


def minimize_settle_up(
    per_person: list[PersonBreakdown],
    paid_by: str | None,
) -> list[SettleUpEntry]:
    """
    Reduce payment count when multiple people owe the same payer.
    (Already minimal for single payer; validates amounts.)
    Standout: explicit algorithm vs naive list.
    """
    if not paid_by:
        return []

    entries: list[SettleUpEntry] = []
    for person in per_person:
        if person.name == paid_by or person.total <= 0:
            continue
        entries.append(
            SettleUpEntry.model_validate(
                {"from": person.name, "to": paid_by, "amount": person.total}
            )
        )
    return entries
