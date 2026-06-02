# Prompt Log — Fair Split

| # | Change | Why |
|---|--------|-----|
| 1 | Single prompt for receipt + description + totals | Model returned wrong GST and invented a settle-up payer |
| 2 | Split into receipt extraction vs description parsing prompts | Vision task and NLP task need different schemas; reduces hallucinated math |
| 3 | Added strict JSON schema + `response_mime_type: application/json` | Fewer parse failures from Gemini |
| 4 | Receipt prompt: explicit discount sign rule (negative) | Model returned +228 for WELCOME15 instead of −228 |
| 5 | Description prompt: output `assignments[]` with `consumers` + `fraction` | Enables deterministic equal/half splits in code |
| 6 | Added fuzzy item matching (`rapidfuzz`) post-parse | “pasta” ↔ “Penne Arrabiata” without re-prompting |
| 7 | Moved all rupee arithmetic to Python calculator | Model mis-added R3 line items by ₹20 in early tests |
| 8 | Added reconciliation + mandatory flags | Surfaces line-sum ≠ subtotal and missing payer instead of guessing |
| 9 | Temperature 0.1 | More stable extraction on repeated runs |

## Did the model do the arithmetic?

**No.** The model only:
1. Extracts structured receipt fields (items, subtotal, service, GST, discount, grand total)
2. Parses the description into people, item assignments, and payer

**All money math runs in Python** (`calculator.py`):
- Per-person subtotals from item assignments
- Service + tax + discount allocated proportionally to subtotal
- Rupee rounding with documented absorption rule
- Settle-up and reconciliation checks

**Why:** LLMs routinely mis-sum line items and tax. For a fintech-style bill split, deterministic code is the only acceptable source of totals. The model’s job is unstructured → structured; code’s job is structured → correct rupees.
