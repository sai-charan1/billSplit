# Fair Split

Fair Split turns a receipt photo + plain-English description into a reconciled per-person split with tax/service/discount allocation and settle-up.

## Live links

- **App:** [https://bill-split-theta.vercel.app/](https://bill-split-theta.vercel.app/)
- **API:** [https://billsplit-l46n.onrender.com](https://billsplit-l46n.onrender.com) · [OpenAPI `/docs`](https://billsplit-l46n.onrender.com/docs)

## Assignment contract endpoint

`POST /split` returns the exact required shape:

- `per_person`
- `grand_total`
- `reconciliation`
- `paid_by`
- `settle_up`
- `assumptions`
- `flags`

Example:

```bash
curl -X POST https://billsplit-l46n.onrender.com/split \
  -H "Content-Type: application/json" \
  -d '{
    "receipt_base64": "<base64 image bytes>",
    "description": "Four of us: Aman, Priya, Karan, Sara. The Gulab Jamun was shared just by Priya and Karan. Everything else was common to all four. Priya paid."
  }'
```

## Extra product endpoint (not required, useful for demo)

`POST /split/enriched` includes:

- bill health score (`A–D`, `0–100`)
- per-person explanation strings
- WhatsApp-ready share message
- model/provider used

This is for better UX and reviewer visibility. Core grading should use `/split`.

## Tech stack

- Backend: FastAPI + Pydantic
- Vision/Text extraction: Groq (primary), Gemini (fallback)
- Deterministic split math: Python (`calculator.py`)
- Frontend: Vite + vanilla JS
- OCR fallback: Tesseract (`pytesseract`)

## Project structure

```text
backend/app/
  main.py               # API routes
  pipeline.py           # end-to-end orchestration
  llm.py                # provider chain + parsing
  prompts.py            # centralized LLM prompts
  receipt_normalize.py  # rate-vs-total, S.Tax, GST normalization
  description_rules.py  # deterministic fallback parser
  calculator.py         # all rupee math + reconciliation
  bill_health.py        # trust score + checks
  explain.py            # per-person explanations/share text
  groq_client.py
  gemini_client.py
frontend/
docs/
  EDGE_CASES.md
  PROMPT_LOG.md
  AI_FAILURES.md
  STANDOUT.md
```

## Local run

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload --app-dir .
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`  
API URL: `http://localhost:8000`

## Environment variables

Use `.env.example`.

Required (recommended):
- `GROQ_API_KEY` (free key from `https://console.groq.com/keys`)

Optional fallback:
- `GEMINI_API_KEY` (from `https://aistudio.google.com/app/apikey`)

## Deployment (free)

- API: Render (Dockerfile included)
- Frontend: Vercel (`frontend/` root)

## Is demo sample required?

No. The assignment does not require demo sample selectors or hardcoded sample bills.  
This repo is submission-focused and processes uploaded images directly.

## How I tested

I tested this project at three levels: unit tests, edge-case scenario tests, and manual UI checks.

### 1) Automated tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Current suite covers:
- deterministic calculator arithmetic and reconciliation
- no-payer behavior + settle-up constraints
- pooled duplicate item names (different rates/rows)
- quantity assignments (`2 each`)
- exclusion patterns (`all except X`)
- equal split language (`all of us ate all`, `split all into 3`)
- receipt normalization:
  - line totals vs rate×qty mismatch
  - service tax (`S.Tax`) inference
  - CGST+SGST composition
- contract schema checks for `/split`

### 2) Edge-case receipts validated

- **Cedarstay Hotels** style bills: repeated item rows with different per-unit pricing.
- **Liquor Street** style bills: rightmost line totals include markup + `S.Tax` footer.
- Natural-language variations:
  - lowercase names without commas
  - "3 of us went ..."
  - "all ate all split into 3"

### 3) Manual product checks

- upload image + description flow
- per-person table consistency
- settle-up generation when payer exists
- flag surfacing on ambiguity/mismatch
- enriched endpoint rendering (bill health, explanations, share message)

## Submission artifacts

- `docs/EDGE_CASES.md`
- `docs/PROMPT_LOG.md`
- `docs/AI_FAILURES.md`
- `docs/STANDOUT.md`

