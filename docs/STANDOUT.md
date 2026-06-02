# What Makes This Submission Stand Out

Written for evaluators (product + engineering at a fintech like Epifi).

---

## 1. The core insight (what they want to hear)

> **"Splitting a bill is a small ledger. AI extracts structure; code settles money."**

- LLM never returns final rupee totals
- Python enforces fairness rules + reconciliation
- When unsure → **flag**, never guess

This is the same mental model as payments: extract → validate → settle → audit trail.

---

## 2. Production architecture (not a hackathon script)

```
Image + Description
       ↓
┌──────────────────────────────────────┐
│  Provider chain: Groq → Gemini → Rules │
│  (vision + text, with fallbacks)       │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Receipt normalizer (India formats)    │
│  Rate×Qty vs Total column, S.Tax, GST  │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Description parser + rule refinement  │
│  quantities, except, equal split       │
└──────────────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Deterministic calculator (calculator.py)│
│  pool duplicate items, proportional tax │
└──────────────────────────────────────┘
       ↓
  SplitResponse + Bill Health + Explain
```

**Modules (standard layout):**

| Module | Role |
|--------|------|
| `pipeline.py` | Orchestration |
| `prompts.py` | Single source of truth for LLM prompts |
| `receipt_normalize.py` | India bill format fixes |
| `description_rules.py` | Deterministic NLP fallback |
| `calculator.py` | All rupee math |
| `bill_health.py` | Trust score 0–100 |
| `explain.py` | Human-readable breakdown |
| `groq_client.py` / `gemini_client.py` | Provider adapters |

---

## 3. Standout features (beyond the assignment spec)

### A. Bill Health Score (0–100, grade A–D)

Answers: *"Can I trust this split?"*

Checks: line items vs subtotal, reconciliation, payer stated, critical flags.

**Why HR cares:** Shows product thinking — users need confidence before sending money.

### B. Per-person explanations

*"Sai: Food ₹345 + Service ₹18 + Tax ₹18 = ₹381"*

**Why HR cares:** Reduces disputes at the table; explainability is mandatory in fintech.

### C. WhatsApp share message (one tap)

Copy-ready text for group chats with settle-up lines.

**Why HR cares:** Real users share splits on WhatsApp — you shipped the last mile.

### D. Dual API

- `POST /split` — exact assignment contract
- `POST /split/enriched` — UI + demo extras

**Why HR cares:** You respected the spec AND built product value.

### E. Multi-provider resilience

Groq (free, vision) → Gemini → Rules → Tesseract OCR

**Why HR cares:** Production systems don't depend on one API quota.

---

## 4. Edge cases you solved (real bills, not just R1–R4)

| Scenario | Your bill | Fix |
|----------|-----------|-----|
| Tax-inclusive line Total vs Rate×Qty | Liquor Street | `receipt_normalize.py` scales to subtotal |
| S.Tax not in service_charge field | Liquor Street | Inferred from footer |
| Equal split "all ate all split into 3" | Liquor Street | Rule parser + no ugly ×0.333 labels |
| Duplicate item rows, different prices | Cedarstay | Item pooling by name |
| "2 biryanis each" | Cedarstay | `quantity_per_consumer` |
| "all except X ate Y" | Cedarstay | Exclusion parser |
| Lowercase names, no commas | User bills | `_normalize_name`, space-separated people |
| CGST + SGST separate | Many Indian bills | Summed into `gst` field |

Full list: [EDGE_CASES.md](./EDGE_CASES.md)

---

## 5. What you could say in the interview (30 seconds)

*"I built Fair Split as a small ledger: vision LLM extracts structure, Python does every rupee calculation and refuses to answer if reconciliation fails. I tested on messy real bills — hotel receipts with S.Tax, duplicate biryani lines, equal splits — and added bill health scoring and WhatsApp share because that's what users actually need after the math works."*

---

## 6. Optional stretch ideas (if you have 2 more hours)

| Idea | Effort | Impact |
|------|--------|--------|
| Minimize settle-up transactions (debt graph) | Medium | Algorithmic flair |
| UPI deep link per settle-up row | Low | Very Epifi |
| Receipt blur detection → "retake photo" | Low | UX polish |
| 10-line "How I tested" video in README | Low | Huge for HR |

---

## 7. Links to include in submission email

- Public GitHub repo
- Deployed API: `POST /split` and `POST /split/enriched`
- Deployed frontend with Bill Health + Copy share
- `docs/EDGE_CASES.md`, `docs/PROMPT_LOG.md`, `docs/AI_FAILURES.md`
- This file: `docs/STANDOUT.md`
