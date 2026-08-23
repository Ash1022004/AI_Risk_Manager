from __future__ import annotations

import threading
import traceback

from agent.groq_agent import review_case
from app import store
from app.redis_client import ack_review, claim_review, enqueue_review, reset_redis, requeue_inflight
from ml.scorer import score_merchant

PROTECTED = ["overridden"]


def _already_overridden(review_id: str) -> bool:
    current = store.get_review(review_id)
    return bool(current and current.get("status") == "overridden")


def process_review(review_id: str) -> None:
    review = store.get_review(review_id)
    if not review:
        return
    if review.get("status") == "overridden":
        return
    merchant = store.get_merchant(review["merchant_id"])
    if not merchant:
        store.update_review(
            review_id,
            {"status": "failed", "explanation": "Merchant missing."},
            unless_statuses=PROTECTED,
        )
        store.add_event(review_id, "failed", {"reason": "merchant_missing"})
        return

    try:
        store.update_review(review_id, {"status": "scoring"}, unless_statuses=PROTECTED)
        if _already_overridden(review_id):
            return
        store.add_event(review_id, "scoring", {})
        score = score_merchant(merchant.get("features") or {})
        store.update_review(
            review_id,
            {
                "status": "agent_reviewing",
                "risk_score": score["risk_score"],
                "risk_band": score["risk_band"],
                "feature_drivers": score["feature_drivers"],
            },
            unless_statuses=PROTECTED,
        )
        if _already_overridden(review_id):
            return
        store.add_event(
            review_id,
            "scored",
            {"risk_score": score["risk_score"], "risk_band": score["risk_band"]},
        )

        similar = store.similar_merchants(score["features"], exclude_id=merchant["id"])
        decision = review_case(merchant=merchant, score=score, similar=similar)
        if _already_overridden(review_id):
            return
        store.update_review(
            review_id,
            {
                "status": "decided",
                "recommended_action": decision["recommended_action"],
                "explanation": decision["explanation"],
                "policy_hits": decision["policy_hits"],
                "agent_trace": decision["agent_trace"],
            },
            unless_statuses=PROTECTED,
        )
        if _already_overridden(review_id):
            return
        store.add_event(
            review_id,
            "decided",
            {"action": decision["recommended_action"]},
        )
    except Exception as exc:
        store.update_review(
            review_id,
            {"status": "failed", "explanation": str(exc)},
            unless_statuses=PROTECTED,
        )
        store.add_event(review_id, "failed", {"error": str(exc), "trace": traceback.format_exc()[-500:]})


def run_worker(stop: threading.Event) -> None:
    try:
        requeue_inflight()
    except Exception:
        reset_redis()
    while not stop.is_set():
        try:
            review_id = claim_review(timeout=2)
        except Exception:
            reset_redis()
            if stop.wait(2):
                break
            continue
        if not review_id:
            continue
        try:
            process_review(review_id)
            ack_review(review_id)
        except Exception:
            try:
                enqueue_review(review_id)
                ack_review(review_id)
            except Exception:
                reset_redis()
