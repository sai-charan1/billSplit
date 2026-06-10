# Where the AI was wrong

Three issues I hit during testing and how I fixed them.

### 1. Discount sign

The model returned the WELCOME15 discount as **+228** instead of **−228**.  
Reconciliation failed immediately (components did not match ₹1436).  
**Fix:** Clarified in the receipt prompt that discounts must be negative; added a small post-parse check for coupon-style labels.

### 2. Service charge as a line item

On a noisy receipt, the model put “Service Charge” inside `items[]` as well as in the footer, so line sums overshot the subtotal.  
**Fix:** Prompt says tax and service belong in footer fields, not as food line items. Calculator only uses footer `service_charge` and `gst` for allocation.

### 3. Wrong amount on a qty line

On a beer line (qty 2), the model read **₹600** instead of **₹500**.  
Line sum did not match printed subtotal → flagged before trusting the split.  
**Fix:** Lower temperature, separate `qty` and `amount` in schema, and keep reconciliation mandatory.

**Takeaway:** Mistakes were in reading the bill, not in adding numbers. That is why totals stay in code and every response is checked against the printed grand total.
