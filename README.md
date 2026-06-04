# Fair Split

Upload a restaurant bill photo, describe who ate what in plain English, and get a per-person split with tax/service/discount and settle-up.

**Try it:** [bill-split-theta.vercel.app](https://bill-split-theta.vercel.app/)  
**API:** [billsplit-l46n.onrender.com](https://billsplit-l46n.onrender.com) · [docs](https://billsplit-l46n.onrender.com/docs)

No login needed — open the app and upload a receipt.

---

## How it works

1. Vision model reads the receipt (items, subtotal, GST, service, discount, grand total).
2. Another pass parses your description (people, who shared which item, who paid).
3. All rupee math runs in Python — the model does not calculate final amounts.
4. If something does not add up, the API returns flags instead of guessing.

---

## Tech stack

- **Backend:** FastAPI, Pydantic
- **LLM:** Groq (primary), Gemini (fallback), rule-based parser as last resort
- **Frontend:** Vite + vanilla JS
- **Deploy:** Render (API), Vercel (UI)

---

## Run locally

**Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # add GROQ_API_KEY (and optionally GEMINI_API_KEY)
uvicorn app.main:app --reload --app-dir .
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

API: `http://localhost:8000` · UI: `http://localhost:5173`

Set `VITE_API_URL` in `.env` if the frontend should point at a remote API.

---

## API

Main endpoint: `POST /split`

```bash
curl -X POST https://billsplit-l46n.onrender.com/split \
  -H "Content-Type: application/json" \
  -d '{
    "receipt_base64": "<base64 image>",
    "description": "Four of us: Aman, Priya, Karan, Sara. Gulab Jamun only for Priya and Karan. Rest split equally. Priya paid."
  }'
```

Response includes `per_person`, `grand_total`, `reconciliation`, `paid_by`, `settle_up`, `assumptions`, and `flags`.

There is also `POST /split/enriched` for the UI (bill health score, short explanations, share text).

---

## Testing

```bash
cd backend && source .venv/bin/activate && pytest -q
```

I covered calculator logic, reconciliation, duplicate line items on the same bill, quantity splits (“2 each”), “all except X”, equal-split wording, and receipt normalization (rate×qty vs printed total, S.Tax, CGST+SGST). I also checked the live app with a few real bill photos.

---

## Notes

- First request on Render free tier can be slow after idle (~30–60s).
- Blurry or cropped receipts may misread line amounts — check `flags` in the response.
- Only one payer is supported in settle-up for now.
