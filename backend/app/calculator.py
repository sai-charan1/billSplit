from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz, process

from app.models import (
    DescriptionData,
    ItemAssignment,
    PersonBreakdown,
    ReceiptData,
    ReceiptLineItem,
    Reconciliation,
    SettleUpEntry,
    SplitResponse,
)


@dataclass
class PersonLedger:
    name: str
    item_lines: list[str] = field(default_factory=list)
    subtotal: float = 0.0


@dataclass
class ItemPool:
    name: str
    total_qty: float
    total_amount: float
    indices: list[int]

    @property
    def unit_price(self) -> float:
        if self.total_qty <= 0:
            return 0.0
        return self.total_amount / self.total_qty


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:].lower()


def _normalize_people(description: DescriptionData) -> DescriptionData:
    people = [_normalize_name(p) for p in description.people]
    paid_by = _normalize_name(description.paid_by) if description.paid_by else None
    assignments = []
    for a in description.assignments:
        assignments.append(
            ItemAssignment(
                item_ref=a.item_ref,
                consumers=[_normalize_name(c) for c in a.consumers],
                fraction=a.fraction,
                quantity_per_consumer=a.quantity_per_consumer,
                note=a.note,
            )
        )
    return DescriptionData(
        people=people,
        paid_by=paid_by,
        assignments=assignments,
        assumptions=description.assumptions,
        flags=description.flags,
    )


def _item_pools(receipt_items: list[ReceiptLineItem]) -> dict[str, ItemPool]:
    pools: dict[str, ItemPool] = {}
    for idx, item in enumerate(receipt_items):
        key = item.name.strip().lower()
        if key not in pools:
            pools[key] = ItemPool(name=item.name, total_qty=0.0, total_amount=0.0, indices=[])
        pools[key].total_qty += item.qty
        pools[key].total_amount += item.amount
        pools[key].indices.append(idx)
    return pools


def _find_pool(item_ref: str, receipt_items: list[ReceiptLineItem]) -> ItemPool | None:
    pools = _item_pools(receipt_items)
    if not pools:
        return None

    ref_lower = item_ref.strip().lower()
    if ref_lower in pools:
        return pools[ref_lower]

    names = list(pools.keys())
    match = process.extractOne(item_ref, names, scorer=fuzz.token_set_ratio)
    if match and match[1] >= 55:
        return pools[match[0]]

    for key, pool in pools.items():
        if ref_lower in key or key in ref_lower:
            return pool
    return None


def _assign_pool_units(
    ledger: dict[str, PersonLedger],
    pool: ItemPool,
    consumers: list[str],
    units_per_consumer: float,
    *,
    pool_remaining: dict[str, float],
    assumptions: list[str],
) -> None:
    if not consumers or units_per_consumer <= 0:
        return

    key = pool.name.strip().lower()
    requested = units_per_consumer * len(consumers)
    available = pool_remaining.get(key, pool.total_qty)
    units_to_assign = min(requested, available)
    if units_to_assign <= 0:
        return

    if units_to_assign < requested - 0.001:
        assumptions.append(
            f"Only {available:.0f} units of '{pool.name}' on bill; assigned {units_to_assign:.0f} of {requested:.0f} requested"
        )

    per_person_units = units_to_assign / len(consumers)
    unit_price = pool.unit_price
    label = pool.name
    if units_per_consumer != 1.0:
        label = f"{pool.name} (×{units_per_consumer:g})"

    for person in consumers:
        if person not in ledger:
            ledger[person] = PersonLedger(name=person)
        cost = unit_price * per_person_units
        ledger[person].subtotal += cost
        ledger[person].item_lines.append(label)

    pool_remaining[key] = available - units_to_assign


def _assign_item_cost(
    ledger: dict[str, PersonLedger],
    item: ReceiptLineItem,
    consumers: list[str],
    fraction: float,
    display_suffix: str = "",
) -> None:
    if not consumers:
        return

    share = (item.amount * fraction) / len(consumers)
    label = item.name if not display_suffix else f"{item.name} ({display_suffix})"

    for person in consumers:
        if person not in ledger:
            ledger[person] = PersonLedger(name=person)
        ledger[person].subtotal += share
        ledger[person].item_lines.append(label)


def _resolve_consumers(assignment: ItemAssignment, all_people: list[str]) -> list[str]:
    return [_normalize_name(p) for p in assignment.consumers if _normalize_name(p) in all_people]


def _build_ledgers(
    receipt: ReceiptData,
    description: DescriptionData,
    assumptions: list[str],
    flags: list[str],
) -> dict[str, PersonLedger]:
    people = [_normalize_name(p) for p in description.people]
    ledger = {name: PersonLedger(name=name) for name in people}
    assigned_indices: set[int] = set()
    pools = _item_pools(receipt.items)
    pool_remaining = {k: p.total_qty for k, p in pools.items()}

    for assignment in description.assignments:
        ref_lower = assignment.item_ref.lower().strip()
        is_catch_all = ref_lower in {
            "everything else",
            "the rest",
            "rest",
            "remaining items",
            "all other items",
            "common to all",
            "shared by all",
        }

        if is_catch_all:
            consumers = _resolve_consumers(assignment, people) or people
            for idx, item in enumerate(receipt.items):
                if idx in assigned_indices:
                    continue
                _assign_item_cost(ledger, item, consumers, assignment.fraction)
                assigned_indices.add(idx)
            continue

        pool = _find_pool(assignment.item_ref, receipt.items)
        if pool is None:
            flags.append(f"Item '{assignment.item_ref}' mentioned in description but not found on receipt")
            continue

        consumers = _resolve_consumers(assignment, people)
        if not consumers:
            consumers = people
            assumptions.append(
                f"No valid consumers for '{assignment.item_ref}'; split equally among all {len(people)} people"
            )

        units = assignment.quantity_per_consumer
        if units != 1.0 or len(pool.indices) > 1:
            _assign_pool_units(
                ledger,
                pool,
                consumers,
                units * assignment.fraction,
                pool_remaining=pool_remaining,
                assumptions=assumptions,
            )
            for idx in pool.indices:
                assigned_indices.add(idx)
            if pool.name.lower() != assignment.item_ref.lower():
                assumptions.append(f"'{assignment.item_ref}' pooled across {len(pool.indices)} receipt line(s) of '{pool.name}'")
            continue

        matched = receipt.items[pool.indices[0]]
        idx = pool.indices[0]
        assigned_indices.add(idx)
        suffix = ""
        if assignment.fraction < 0.999:
            suffix = "½" if assignment.fraction == 0.5 else f"{assignment.fraction:.2f} share"
        _assign_item_cost(ledger, matched, consumers, assignment.fraction, display_suffix=suffix)

    for idx, item in enumerate(receipt.items):
        if idx in assigned_indices:
            continue
        assumptions.append(f"Unassigned item '{item.name}' split equally among all diners")
        _assign_item_cost(ledger, item, people, 1.0)
        assigned_indices.add(idx)

    return ledger


def _allocate_proportional(person_subtotals: dict[str, float], pool: float) -> dict[str, float]:
    total = sum(person_subtotals.values())
    if total <= 0 or pool == 0:
        return {name: 0.0 for name in person_subtotals}
    return {name: (sub / total) * pool for name, sub in person_subtotals.items()}


def _round_to_target(values: dict[str, float], target: int) -> dict[str, int]:
    """Largest-remainder rounding so integer shares sum exactly to target."""
    names = list(values.keys())
    if not names:
        return {}

    raw_sum = sum(values.values())
    if raw_sum <= 0:
        return {name: 0 for name in names}

    scaled = {name: (values[name] / raw_sum) * target for name in names}
    floored = {name: int(scaled[name]) for name in names}
    remainder = target - sum(floored.values())

    if remainder > 0:
        order = sorted(names, key=lambda n: scaled[n] - floored[n], reverse=True)
        for i in range(remainder):
            floored[order[i % len(order)]] += 1
    elif remainder < 0:
        order = sorted(names, key=lambda n: scaled[n] - floored[n])
        for i in range(-remainder):
            floored[order[i % len(order)]] -= 1

    return floored


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def compute_split(
    receipt: ReceiptData,
    description: DescriptionData,
    extra_assumptions: list[str] | None = None,
    extra_flags: list[str] | None = None,
) -> SplitResponse:
    description = _normalize_people(description)
    assumptions = list(extra_assumptions or []) + list(description.assumptions)
    flags = _dedupe(list(extra_flags or []) + list(description.flags))

    line_sum = sum(item.amount for item in receipt.items)
    if abs(line_sum - receipt.subtotal) > 1.0:
        flags.append(
            f"Extracted line items sum to ₹{line_sum:.0f} but printed subtotal is ₹{receipt.subtotal:.0f} "
            f"— ₹{abs(line_sum - receipt.subtotal):.0f} unexplained"
        )

    computed_before_round = (
        receipt.subtotal + receipt.service_charge + receipt.gst + receipt.discount + receipt.round_off
    )
    if abs(computed_before_round - receipt.grand_total) > 1.5:
        flags.append(
            f"Computed bill total ₹{computed_before_round:.2f} differs from printed grand total "
            f"₹{receipt.grand_total:.0f}"
        )

    if not description.people:
        flags.append("No diners identified in description")

    ledger = _build_ledgers(receipt, description, assumptions, flags)
    people = description.people or list(ledger.keys())

    person_subtotals = {name: ledger[name].subtotal for name in people}
    subtotal_sum = sum(person_subtotals.values())

    if abs(subtotal_sum - receipt.subtotal) > 5.0:
        flags.append(
            f"Assigned food subtotals sum to ₹{subtotal_sum:.0f} but bill subtotal is ₹{receipt.subtotal:.0f}"
        )

    service_shares = _allocate_proportional(person_subtotals, receipt.service_charge)
    tax_shares = _allocate_proportional(person_subtotals, receipt.gst)
    discount_shares = _allocate_proportional(person_subtotals, receipt.discount)

    absorb_person = description.paid_by or people[0]
    assumptions.append(f"Rounding to nearest rupee; leftover paise absorbed by '{absorb_person}'")

    grand_total = int(round(receipt.grand_total))
    sub_int = _round_to_target(person_subtotals, int(round(receipt.subtotal)))
    svc_int = _round_to_target(service_shares, int(round(receipt.service_charge)))
    tax_int = _round_to_target(tax_shares, int(round(receipt.gst)))
    disc_int = _round_to_target(discount_shares, int(round(receipt.discount)))

    raw_totals = {
        name: sub_int[name] + svc_int[name] + tax_int[name] + disc_int[name] for name in people
    }
    rounded_totals = _round_to_target(
        {name: float(raw_totals[name]) for name in people},
        grand_total,
    )

    per_person: list[PersonBreakdown] = []
    for name in people:
        total = max(0, rounded_totals[name])
        per_person.append(
            PersonBreakdown(
                name=name,
                items=sorted(set(ledger[name].item_lines)) if ledger[name].item_lines else ["(no items matched)"],
                subtotal=sub_int[name],
                tax_share=tax_int[name],
                service_share=svc_int[name],
                discount_share=disc_int[name],
                total=total,
            )
        )

    sum_totals = sum(p.total for p in per_person)
    matches = abs(sum_totals - grand_total) <= 0

    if not matches:
        flags.append(
            f"After rounding, person totals sum to ₹{sum_totals} but bill grand total is ₹{grand_total}"
        )

    paid_by = description.paid_by
    if not paid_by:
        flags.append("No payer stated in description — settle-up cannot be finalized")

    settle_up = _compute_settle_up(per_person, paid_by, flags)

    return SplitResponse(
        per_person=per_person,
        grand_total=grand_total,
        reconciliation=Reconciliation(
            sum_of_person_totals=sum_totals,
            matches_bill=matches and abs(line_sum - receipt.subtotal) <= 1.0,
        ),
        paid_by=paid_by,
        settle_up=settle_up,
        assumptions=_dedupe(assumptions),
        flags=_dedupe(flags),
    )


def _compute_settle_up(
    per_person: list[PersonBreakdown],
    paid_by: str | None,
    flags: list[str],
) -> list[SettleUpEntry]:
    if not paid_by:
        return []

    known_names = {p.name for p in per_person}
    if paid_by not in known_names:
        flags.append(f"Payer '{paid_by}' is not among identified diners")
        return []

    entries: list[SettleUpEntry] = []
    for person in per_person:
        if person.name == paid_by:
            continue
        if person.total <= 0:
            continue
        entries.append(
            SettleUpEntry.model_validate(
                {"from": person.name, "to": paid_by, "amount": person.total}
            )
        )
    return entries
