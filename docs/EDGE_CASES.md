# Edge cases

How I handled tricky inputs while building this.

### No payer in the description

If nobody is named as payer → `paid_by` is null, `settle_up` is empty, and a flag explains that settle-up cannot be finalized.

### Item in description but not on the bill

e.g. description says “sushi” but the receipt has no match → flagged; that item is not charged to anyone.

### Line items do not match printed subtotal

OCR/vision sometimes sums items differently from the printed subtotal. The split still runs on extracted items, but `reconciliation.matches_bill` stays false and a flag shows the gap.

### “Everything else” / catch-all

Named items go to the people you specify; remaining lines are split equally across everyone in the group.

### Shared item for a subset only

e.g. two beers for two people → that line amount is divided only between them, not the whole table.

### Bill-level discount (coupon %)

Discount is stored as a negative amount and allocated in proportion to each person’s food subtotal.

### Fuzzy item names

Description says “pasta”, receipt says “Penne Arrabiata” → matched with `rapidfuzz`; logged in `assumptions`.

### Unassigned receipt lines

If the description does not mention some items, those lines are split equally among all diners (with an assumption note).

### Rounding

Per-person amounts are rounded to whole rupees; small remainder is adjusted so the total still matches the bill grand total.

### Equal split phrasing

Handles wording like “all of us ate everything” or “split equally among 3” without needing exact item names.

### Duplicate rows, different prices

Some hotel/restaurant bills repeat the same dish with different rates. Items are pooled by name before splitting.

### Quantity per person

e.g. “2 biryanis each for A and B” → quantity is applied per consumer, not as a blind equal split of one line.

### Service tax (S.Tax) on liquor-style bills

When service tax is in the footer but not in `service_charge`, normalization tries to pick it up from the printed breakdown.

### Provider failure

If Groq/Gemini hit quota or errors, the pipeline tries the next provider, then OCR + rules. It returns flags rather than made-up totals.

### Not handled in v1

- Two payers splitting the bill (“Priya paid half, Karan paid half”)
- Cash tip mentioned only in text, not on the receipt
- Payer name not in the diner list (flagged, no settle-up)
