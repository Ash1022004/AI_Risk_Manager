# AI Risk Manager

Scoped Razorpay Bumblebee: LightGBM scores merchant-risk signals, a Groq tool-calling agent explains the case and recommends **approve / hold / escalate**, and a Next.js ops queue shows the live review.

## Architecture

Merchant submit → FastAPI → Redis Cloud queue → worker (LightGBM + SHAP-style contributions + Groq tools + policy floor) → Supabase → dashboard.

XGBoost/LightGBM is the scorer. The LLM is the reviewer, not the ranker. Policy is a hard guardrail: the agent cannot approve through a hard-fail rule.

## One-time setup

Keys live in `backend/.env` (never commit it): Groq, Redis Cloud, Supabase URL + secret key, optional Kaggle token.

1. In the [Supabase SQL editor](https://supabase.com/dashboard), paste and run `backend/app/schema.sql`.
2. Accept [IEEE-CIS competition rules](https://www.kaggle.com/competitions/ieee-fraud-detection/rules) if you want the real dataset. Otherwise training uses synthetic merchants.

```bash
cd backend
uv sync
uv run python -m ml.download_and_train
uv run python -m app.seed
uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Submit the high-risk seed, then the clean seed. Open a case to see score, drivers, policy, and the agent write-up.

`GET /health` reports Redis, Supabase tables, Groq status, and whether the model file exists. If Supabase tables are missing, reviews persist in Redis until you apply `schema.sql` — the API re-checks and switches over without a restart.

If a case shows a Groq `401 invalid_api_key` in the agent trace, replace `GROQ_API_KEY` in `backend/.env` with a key from [console.groq.com](https://console.groq.com). Scoring and policy still decide the action without Groq.

## Demo path

1. Submit **high-risk** → score in the high band → agent **escalate**.
2. Submit **clean** → low score → **approve**.
3. Open a case and use an override to show human-in-the-loop.
