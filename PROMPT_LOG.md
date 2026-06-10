# Prompt log

Changes I made to prompts while iterating on the project.

| Step | What I changed | Reason |
|------|----------------|--------|
| 1 | Started with one big prompt for receipt + description + totals | Model got GST wrong and invented a payer |
| 2 | Split into receipt extraction vs description parsing | Different tasks, cleaner JSON, less mixed-up math |
| 3 | Forced JSON output (`application/json`) | Fewer broken responses from Gemini |
| 4 | Told the model discount must be negative when it reduces the bill | It returned +228 for a coupon once |
| 5 | Description output: `assignments` with `consumers` and `fraction` | Lets Python do equal/half splits reliably |
| 6 | Fuzzy match on item names after parse (`rapidfuzz`) | “pasta” vs “Penne Arrabiata” without re-asking the model |
| 7 | Moved all rupee math to `calculator.py` | Model was off by tens of rupees on line totals |
| 8 | Always return reconciliation + flags | Surfaces mismatch instead of silent wrong answers |
| 9 | Temperature 0.1 | More stable on repeated runs |

## Does the model do the arithmetic?

No. It only:

1. Extracts receipt fields (items, subtotal, service, GST, discount, grand total)
2. Parses the description into people, assignments, and payer

Everything involving money is in Python: item allocation, tax/service/discount share, rounding, settle-up, and checks against the printed total.
