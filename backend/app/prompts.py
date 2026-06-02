"""Centralized LLM prompts — single source of truth for receipt + description extraction."""

COMBINED_PROMPT = """You are a restaurant bill assistant for Indian receipts (INR ₹).

Given a receipt IMAGE and a plain-English description of who had what, return ONE JSON object:

{
  "receipt": {
    "restaurant": "string or null",
    "items": [{"name": "string", "qty": number, "amount": number}],
    "subtotal": number,
    "service_charge": number,
    "service_rate_pct": number or null,
    "gst": number,
    "discount": number,
    "discount_label": "string or null",
    "round_off": number,
    "grand_total": number
  },
  "description": {
    "people": ["diner names"],
    "paid_by": "payer name or null",
    "assignments": [
      {"item_ref": "string", "consumers": ["names"], "fraction": 1.0, "quantity_per_consumer": 1.0}
    ],
    "assumptions": [],
    "flags": []
  }
}

RECEIPT EXTRACTION (India-specific):
- item amount = Rate × Qty (base price BEFORE per-line service/VAT markup)
- Do NOT use the rightmost Total column if it already includes 5% service (common on hotel bills)
- Footer fields (NOT line items): Sub Total, Service Charge, S.Tax, Service Tax, CGST, SGST, VAT, Round-off, Grand Total
- Sum CGST + SGST into gst field
- S.Tax / Service Tax → service_charge
- discount negative if it reduces bill
- Extract ALL food items including chicken, roti, drinks — do not skip any row

DESCRIPTION (from text below):
- "N of us went A B C" or "N of us — A, B, C" → people list
- "all ate all" / "split equally" / "split all into N" → item_ref="everything else", all consumers
- "X and Y ate 2 Z each" → quantity_per_consumer: 2
- "all except X ate Y" → consumers = everyone except X
- "X paid" → paid_by
- Match item names to receipt; pool duplicate item names

Description text:
\"\"\"{description}\"\"\"
"""

OCR_RECEIPT_PROMPT = """Structure this OCR text from an Indian restaurant receipt into JSON.

OCR text:
\"\"\"
{ocr_text}
\"\"\"

Return ONLY JSON:
{"restaurant":null,"items":[{"name":"","qty":1,"amount":0}],"subtotal":0,"service_charge":0,
"service_rate_pct":null,"gst":0,"discount":0,"discount_label":null,"round_off":0,"grand_total":0}

Use Rate×Qty for amounts. S.Tax→service_charge. CGST+SGST→gst. discount negative if applicable.
"""

DESCRIPTION_PROMPT = """Parse this bill-split description into JSON.

Description:
\"\"\"{description}\"\"\"

Receipt items:
{items_json}

Return ONLY JSON:
{
  "people": ["names"],
  "paid_by": "name or null",
  "assignments": [{"item_ref": "...", "consumers": ["..."], "fraction": 1.0, "quantity_per_consumer": 1.0}],
  "assumptions": [],
  "flags": []
}
"""
