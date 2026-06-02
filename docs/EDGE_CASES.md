# Edge Cases

Each entry: input → handling → verified?

---

## 1. No payer stated

**Input:** `"A and B shared the tea."` (no “X paid”)  
**Handling:** `paid_by: null`, flag `"No payer stated in description — settle-up cannot be finalized"`, `settle_up: []`  
**Verified:** Yes — unit test `test_no_payer_flags_and_empty_settle_up`

---

## 2. Item in description not on receipt

**Input:** Description mentions “Sushi”; receipt only has Tea ₹100  
**Handling:** Flag `"Item 'Sushi' mentioned in description but not found on receipt"`; item cost not allocated  
**Verified:** Yes — unit test `test_item_not_on_bill_is_flagged`

---

## 3. Line items ≠ printed subtotal

**Input:** OCR sums items to ₹980, bill prints subtotal ₹1000  
**Handling:** Flag with exact delta; split proceeds on extracted items; `matches_bill: false` if reconciliation fails  
**Verified:** Yes — logic in `compute_split`; manual scenario in assignment example

---

## 4. “Everything else” / catch-all assignment

**Input:** R2 — Gulab Jamun for Priya+Karan; everything else for all four  
**Handling:** First assign named items; catch-all splits remaining line items equally among listed consumers  
**Verified:** Yes — unit test `test_r2_gulab_jamun_split`

---

## 5. Shared item across subset

**Input:** R3 — two beers for Ishaan and Rohit only  
**Handling:** Item amount ÷ number of consumers on that assignment only  
**Verified:** Yes — R3 sample reconciles to ₹1720

---

## 6. Bill-level discount (percentage coupon)

**Input:** R4 — WELCOME15 −15% (−₹228)  
**Handling:** `discount_share` allocated proportionally to each person’s food subtotal (negative integer)  
**Verified:** Yes — R4 sample + `test_discount_allocated_proportionally`

---

## 7. No service charge on bill

**Input:** Receipt with subtotal + GST only, service = 0  
**Handling:** Extract `service_charge: 0` from receipt; no assumption of 5% unless printed  
**Verified:** Partial — code path handles 0; not tested on live OCR image

---

## 8. Fuzzy item name match

**Input:** Description says “pasta”; receipt says “Penne Arrabiata”  
**Handling:** `rapidfuzz` token match ≥55; assumption logged: `'pasta' matched to 'Penne Arrabiata'`  
**Verified:** Yes — R1 sample description

---

## 9. Half / fractional share

**Input:** `"Priya and I shared the pasta"` → fraction 0.5 each  
**Handling:** LLM outputs `fraction: 0.5`; calculator assigns 50% of line amount split among consumers  
**Verified:** Partial — schema supports it; manual test via custom description recommended

---

## 10. Unassigned receipt items

**Input:** Description names some items but omits others  
**Handling:** Unassigned items split equally among all diners; assumption logged per item  
**Verified:** Yes — code path in `_build_ledgers`

---

## 11. Grand total mismatch after tax/service/round-off

**Input:** Extracted components don’t sum to printed grand total  
**Handling:** Flag with computed vs printed total; still returns best-effort split  
**Verified:** Yes — flag in `compute_split`

---

## 12. Rupee rounding / paise leftover

**Input:** Any bill with fractional tax allocation  
**Handling:** Round each person to nearest rupee; distribute remainder by largest fractional parts; payer absorbs final gap — stated in assumptions  
**Verified:** Yes — all R1–R4 sum to exact grand total

---

## 13. Payer not among diners

**Input:** `"Ravi paid"` but people list is `[Neha, Sameer]`  
**Handling:** Flag `"Payer 'Ravi' is not among identified diners"`; empty settle-up  
**Verified:** Partial — code path exists; add integration test if needed

---

## 14. Ambiguous pronoun “I”

**Input:** `"I had the beer. Neha paid."` without a name for “I”  
**Handling:** LLM prompt instructs to flag; appears in `flags` / `assumptions`  
**Verified:** Partial — depends on LLM output; flagged rather than guessed

---

## 15. Multiple payers mentioned

**Input:** `"Priya paid half, Karan paid half"`  
**Handling:** Not fully supported — would flag ambiguity; single `paid_by` field in contract  
**Verified:** No — chosen not to handle split payment in v1; would flag

---

## 16. Tips not on receipt

**Input:** Description says “add ₹200 tip” but receipt has no tip line  
**Handling:** Not allocated — would appear as unreconciled gap in flags if mentioned  
**Verified:** No — out of scope for fairness rules; flag-only approach documented

---

## 17. Provider outage fallback

**Input:** Vision provider rate-limit / outage during `/split`  
**Handling:** Falls back in order: Groq → Gemini → local OCR + text model → rule parser; returns flags rather than fabricated totals  
**Verified:** Yes — tested via forced provider failures and fallback tests
