# Where the AI Was Wrong

Three concrete failures from development testing and how they were caught/fixed.

---

## 1. Wrong discount sign (R4)

**What happened:** Gemini extracted WELCOME15 discount as `+228` instead of `−228`.  
**Impact:** Grand total reconciliation would show everyone overpaying; discount shares would add instead of subtract.  
**How caught:** Python check: `subtotal + service + gst + discount + round_off` did not match printed ₹1436.  
**Fix:** Receipt prompt explicitly states: *“discount should be NEGATIVE if it reduces the bill”*. Post-parse clamp: if discount label contains “discount/off/coupon” and value is positive, negate it (optional hardening).

---

## 2. Hallucinated extra line item (R1 test photo)

**What happened:** On a slightly blurry generated receipt, the model added “Service Charge” as a line item in `items[]` and double-counted service.  
**Impact:** Line-item sum exceeded subtotal; per-person food allocation inflated.  
**How caught:** Flag: *“Extracted line items sum to ₹X but printed subtotal is ₹1040”*.  
**Fix:** Receipt prompt clarifies service/GST are footer fields, not line items. Calculator uses footer `service_charge` and `gst` only, not item list, for tax allocation.

---

## 3. Misread beer quantity price (R3)

**What happened:** Model read Craft Beer line as ₹600 instead of ₹500 (confused qty “2” with amount).  
**Impact:** Subtotal off by ₹100; all three diners’ shares skewed.  
**How caught:** Line sum 1660 vs printed subtotal 1560 → flagged before split returned confidently.  
**Fix:** Lower temperature (0.1), JSON schema with separate `qty` and `amount`, and mandatory reconciliation block so API never claims `matches_bill: true` when line sum diverges.

---

## Design takeaway

Every failure above was a **structured extraction** error, not a math error — validating why arithmetic must live in code and extraction must be cross-checked against printed bill totals.
