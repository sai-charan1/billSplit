from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SplitRequest(BaseModel):
    receipt_base64: str
    description: str


class PersonBreakdown(BaseModel):
    name: str
    items: list[str]
    subtotal: int
    tax_share: int
    service_share: int
    discount_share: int
    total: int


class SettleUpEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    amount: int


class Reconciliation(BaseModel):
    sum_of_person_totals: int
    matches_bill: bool


class SplitResponse(BaseModel):
    per_person: list[PersonBreakdown]
    grand_total: int
    reconciliation: Reconciliation
    paid_by: str | None
    settle_up: list[SettleUpEntry]
    assumptions: list[str]
    flags: list[str]


class BillHealthCheck(BaseModel):
    id: str
    ok: bool
    label: str


class BillHealth(BaseModel):
    score: int
    grade: str
    checks: list[BillHealthCheck]


class PersonExplanation(BaseModel):
    name: str
    summary: str
    items: str


class SplitEnrichedResponse(SplitResponse):
    """Assignment contract + product extensions for UI and evaluators."""

    bill_health: BillHealth
    explanations: list[PersonExplanation]
    share_message: str
    model_used: str | None = None


# --- Internal structured models ---


class ReceiptLineItem(BaseModel):
    name: str
    qty: float = 1.0
    amount: float


class ReceiptData(BaseModel):
    restaurant: str | None = None
    items: list[ReceiptLineItem]
    subtotal: float
    service_charge: float = 0.0
    service_rate_pct: float | None = None
    gst: float = 0.0
    discount: float = 0.0
    discount_label: str | None = None
    round_off: float = 0.0
    grand_total: float


class ItemAssignment(BaseModel):
    item_ref: str
    consumers: list[str]
    fraction: float = 1.0
    quantity_per_consumer: float = 1.0
    note: str | None = None


class DescriptionData(BaseModel):
    people: list[str]
    paid_by: str | None = None
    assignments: list[ItemAssignment]
    common_to_all: bool = False
    assumptions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class ParsedBillContext(BaseModel):
    receipt: ReceiptData
    description: DescriptionData
    assumptions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
