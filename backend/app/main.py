from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent.groq_agent import groq_status
from app import store
from app.config import get_settings
from app.db import probe_tables
from app.redis_client import enqueue_review, ping_redis, queue_depth
from app.schemas import MerchantCreate, OverrideBody, ReviewCreate
from app.seeds import SEED_MERCHANTS, get_seed
from app.worker import run_worker
from ml.features import normalize_features
from ml.scorer import model_meta, model_ready

STOP = threading.Event()
WORKER: threading.Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global WORKER
    STOP.clear()
    WORKER = threading.Thread(target=run_worker, args=(STOP,), daemon=True, name="review-worker")
    WORKER.start()
    yield
    STOP.set()
    if WORKER:
        WORKER.join(timeout=4)


app = FastAPI(title="AI Risk Manager", version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _submit_merchant(payload: dict) -> dict:
    features = normalize_features(payload.get("features"))
    merchant = store.create_merchant({**payload, "features": features})
    review = store.create_review(merchant["id"])
    store.add_event(review["id"], "queued", {"merchant": merchant["name"]})
    _enqueue(review["id"])
    return store.attach_merchant(review)


def _enqueue(review_id: str) -> None:
    try:
        enqueue_review(review_id)
    except Exception as exc:
        store.update_review(review_id, {"status": "failed", "explanation": f"Redis enqueue failed: {exc}"})
        raise HTTPException(status_code=503, detail=f"Redis enqueue failed: {exc}") from exc


@app.get("/health")
def health():
    missing = settings.missing()
    redis_ok = ping_redis()
    supabase_ok = probe_tables(force=True)
    groq = groq_status()
    groq_ok = groq.get("status") in {"ok", "unknown"} and bool(settings.groq_api_key)
    return {
        "ok": not missing and redis_ok and model_ready(),
        "missing_env": missing,
        "redis": redis_ok,
        "supabase": supabase_ok,
        "store": store.backend_mode(),
        "model": model_ready(),
        "model_meta": model_meta(),
        "groq": groq,
        "groq_ok": groq_ok,
        "queue_depth": queue_depth() if redis_ok else None,
        "schema_hint": None
        if supabase_ok
        else "Run backend/app/schema.sql in the Supabase SQL editor. The API will pick it up within a few seconds.",
    }


@app.get("/stats")
def stats():
    reviews = store.list_reviews(limit=200)
    actions = {"approve": 0, "hold": 0, "escalate": 0}
    statuses: dict[str, int] = {}
    for review in reviews:
        statuses[review.get("status") or "unknown"] = statuses.get(review.get("status") or "unknown", 0) + 1
        action = review.get("recommended_action")
        if action in actions:
            actions[action] += 1
    redis_ok = ping_redis()
    return {
        "queue_depth": queue_depth() if redis_ok else 0,
        "reviews": len(reviews),
        "actions": actions,
        "statuses": statuses,
        "store": store.backend_mode(),
    }


@app.get("/seeds")
def seeds():
    return [{"slug": item["slug"], "name": item["name"], "category": item["category"]} for item in SEED_MERCHANTS]


@app.post("/merchants")
def create_merchant(body: MerchantCreate):
    return _submit_merchant(body.model_dump())


@app.get("/merchants")
def list_merchants():
    return store.list_merchants()


@app.post("/reviews")
def create_review(body: ReviewCreate):
    if body.seed:
        seed = get_seed(body.seed)
        if not seed:
            raise HTTPException(status_code=404, detail=f"Unknown seed '{body.seed}'")
        return _submit_merchant({k: v for k, v in seed.items() if k != "slug"})
    if body.merchant:
        return _submit_merchant(body.merchant.model_dump())
    if body.merchant_id:
        merchant = store.get_merchant(body.merchant_id)
        if not merchant:
            raise HTTPException(status_code=404, detail="Merchant not found")
        review = store.create_review(merchant["id"])
        store.add_event(review["id"], "queued", {"merchant": merchant["name"]})
        _enqueue(review["id"])
        return store.attach_merchant(review)
    raise HTTPException(status_code=400, detail="Provide seed, merchant, or merchant_id")


@app.get("/reviews")
def list_reviews(status: str | None = None, action: str | None = None):
    rows = store.list_reviews(status=status, action=action)
    return store.attach_many(rows)


@app.get("/reviews/{review_id}")
def get_review(review_id: str):
    review = store.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return store.attach_merchant(review)


@app.post("/reviews/{review_id}/override")
def override_review(review_id: str, body: OverrideBody):
    review = store.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    updated = store.update_review(
        review_id,
        {
            "status": "overridden",
            "human_action": body.action,
            "human_note": body.note,
        },
    )
    store.add_event(review_id, "overridden", {"action": body.action, "note": body.note})
    return store.attach_merchant(updated or review)


@app.get("/schema.sql")
def schema_sql():
    path = Path(__file__).with_name("schema.sql")
    return {"sql": path.read_text()}
