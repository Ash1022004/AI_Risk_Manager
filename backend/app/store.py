from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.db import probe_tables, sb_request
from app.redis_client import get_redis, reset_redis

_lock = threading.Lock()
_merchants: dict[str, dict[str, Any]] = {}
_reviews: dict[str, dict[str, Any]] = {}
_events: dict[str, list[dict[str, Any]]] = {}

MERCHANT_HASH = "risk:store:merchants"
REVIEW_HASH = "risk:store:reviews"
EVENT_HASH = "risk:store:events"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backend_mode() -> str:
    if probe_tables():
        return "supabase"
    try:
        get_redis().ping()
        return "redis"
    except Exception:
        return "memory"


def _redis_hset(hash_key: str, field: str, value: Any) -> None:
    try:
        get_redis().hset(hash_key, field, json.dumps(value, default=str))
    except Exception:
        reset_redis()


def _redis_hget(hash_key: str, field: str) -> Any | None:
    try:
        raw = get_redis().hget(hash_key, field)
        return json.loads(raw) if raw else None
    except Exception:
        reset_redis()
        return None


def _redis_hgetall(hash_key: str) -> dict[str, Any]:
    try:
        raw = get_redis().hgetall(hash_key) or {}
        return {key: json.loads(value) for key, value in raw.items()}
    except Exception:
        reset_redis()
        return {}


def create_merchant(payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        "id": payload.get("id") or str(uuid4()),
        "name": payload["name"],
        "category": payload.get("category") or "general",
        "features": payload.get("features") or {},
        "status": payload.get("status") or "active",
        "source": payload.get("source") or "demo",
        "created_at": payload.get("created_at") or _now(),
    }
    if probe_tables():
        created = sb_request("POST", "merchants", json=row)
        return created[0] if isinstance(created, list) else created
    with _lock:
        _merchants[row["id"]] = row
    _redis_hset(MERCHANT_HASH, row["id"], row)
    return row


def get_merchant(merchant_id: str) -> dict[str, Any] | None:
    if probe_tables():
        rows = sb_request("GET", "merchants", params={"id": f"eq.{merchant_id}", "select": "*"})
        return rows[0] if rows else None
    cached = _merchants.get(merchant_id)
    if cached:
        return cached
    row = _redis_hget(MERCHANT_HASH, merchant_id)
    if row:
        _merchants[merchant_id] = row
    return row


def get_merchants_by_ids(ids: list[str]) -> dict[str, dict[str, Any]]:
    unique = [item for item in dict.fromkeys(ids) if item]
    if not unique:
        return {}
    if probe_tables():
        rows = sb_request(
            "GET",
            "merchants",
            params={"id": f"in.({','.join(unique)})", "select": "*"},
        ) or []
        return {row["id"]: row for row in rows}
    found = {}
    for merchant_id in unique:
        row = get_merchant(merchant_id)
        if row:
            found[merchant_id] = row
    return found


def list_merchants(limit: int = 50) -> list[dict[str, Any]]:
    if probe_tables():
        return sb_request(
            "GET",
            "merchants",
            params={"select": "*", "order": "created_at.desc", "limit": str(limit)},
        ) or []
    rows = list(_redis_hgetall(MERCHANT_HASH).values()) or list(_merchants.values())
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows[:limit]


def create_review(merchant_id: str) -> dict[str, Any]:
    row = {
        "id": str(uuid4()),
        "merchant_id": merchant_id,
        "status": "queued",
        "risk_score": None,
        "risk_band": None,
        "recommended_action": None,
        "explanation": None,
        "feature_drivers": [],
        "policy_hits": [],
        "agent_trace": [],
        "human_action": None,
        "human_note": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    if probe_tables():
        created = sb_request("POST", "reviews", json=row)
        return created[0] if isinstance(created, list) else created
    with _lock:
        _reviews[row["id"]] = row
        _events[row["id"]] = []
    _redis_hset(REVIEW_HASH, row["id"], row)
    _redis_hset(EVENT_HASH, row["id"], [])
    return row


def update_review(
    review_id: str,
    patch: dict[str, Any],
    *,
    unless_statuses: list[str] | None = None,
) -> dict[str, Any] | None:
    patch = {**patch, "updated_at": _now()}
    if probe_tables():
        params: dict[str, str] = {"id": f"eq.{review_id}"}
        if unless_statuses:
            blocked = ",".join(unless_statuses)
            params["status"] = f"not.in.({blocked})"
        rows = sb_request("PATCH", "reviews", params=params, json=patch)
        return rows[0] if rows else get_review(review_id)
    with _lock:
        current = _reviews.get(review_id) or _redis_hget(REVIEW_HASH, review_id)
        if not current:
            return None
        if unless_statuses and current.get("status") in unless_statuses:
            return current
        current.update(patch)
        _reviews[review_id] = current
    _redis_hset(REVIEW_HASH, review_id, current)
    return current


def get_review(review_id: str) -> dict[str, Any] | None:
    if probe_tables():
        rows = sb_request("GET", "reviews", params={"id": f"eq.{review_id}", "select": "*"})
        return rows[0] if rows else None
    cached = _reviews.get(review_id)
    if cached:
        return cached
    row = _redis_hget(REVIEW_HASH, review_id)
    if row:
        _reviews[review_id] = row
    return row


def list_reviews(status: str | None = None, action: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if probe_tables():
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        if status:
            params["status"] = f"eq.{status}"
        if action:
            params["recommended_action"] = f"eq.{action}"
        return sb_request("GET", "reviews", params=params) or []
    rows = list(_redis_hgetall(REVIEW_HASH).values()) or list(_reviews.values())
    if status:
        rows = [r for r in rows if r.get("status") == status]
    if action:
        rows = [r for r in rows if r.get("recommended_action") == action]
    rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return rows[:limit]


def add_event(review_id: str, event_type: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    row = {
        "id": str(uuid4()),
        "review_id": review_id,
        "event_type": event_type,
        "detail": detail or {},
        "created_at": _now(),
    }
    if probe_tables():
        created = sb_request("POST", "review_events", json=row)
        return created[0] if isinstance(created, list) else created
    with _lock:
        bucket = _events.get(review_id)
        if bucket is None:
            bucket = _redis_hget(EVENT_HASH, review_id) or []
        bucket.append(row)
        _events[review_id] = bucket
    _redis_hset(EVENT_HASH, review_id, bucket)
    return row


def list_events(review_id: str) -> list[dict[str, Any]]:
    if probe_tables():
        return (
            sb_request(
                "GET",
                "review_events",
                params={
                    "review_id": f"eq.{review_id}",
                    "select": "*",
                    "order": "created_at.asc",
                },
            )
            or []
        )
    cached = _events.get(review_id)
    if cached is not None:
        return list(cached)
    rows = _redis_hget(EVENT_HASH, review_id) or []
    _events[review_id] = rows
    return list(rows)


def list_events_for_reviews(review_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    unique = [item for item in dict.fromkeys(review_ids) if item]
    if not unique:
        return {}
    if probe_tables():
        rows = (
            sb_request(
                "GET",
                "review_events",
                params={
                    "review_id": f"in.({','.join(unique)})",
                    "select": "*",
                    "order": "created_at.asc",
                },
            )
            or []
        )
        grouped: dict[str, list[dict[str, Any]]] = {review_id: [] for review_id in unique}
        for row in rows:
            grouped.setdefault(row["review_id"], []).append(row)
        return grouped
    return {review_id: list_events(review_id) for review_id in unique}


def similar_merchants(features: dict[str, Any], exclude_id: str | None = None, k: int = 3) -> list[dict[str, Any]]:
    keys = ["kyc_mismatch_rate", "volume_spike", "chargeback_ratio", "device_anomaly", "ip_geo_anomaly"]
    target = [float(features.get(key, 0) or 0) for key in keys]
    scored = []
    for merchant in list_merchants(limit=200):
        if exclude_id and merchant["id"] == exclude_id:
            continue
        other = merchant.get("features") or {}
        vec = [float(other.get(key, 0) or 0) for key in keys]
        dist = sum((a - b) ** 2 for a, b in zip(target, vec)) ** 0.5
        scored.append((dist, merchant))
    scored.sort(key=lambda item: item[0])
    results = []
    for dist, merchant in scored[:k]:
        results.append(
            {
                "id": merchant["id"],
                "name": merchant["name"],
                "distance": round(dist, 4),
                "features": merchant.get("features") or {},
            }
        )
    return results


def attach_merchant(review: dict[str, Any]) -> dict[str, Any]:
    merchant = get_merchant(review["merchant_id"]) if review.get("merchant_id") else None
    return {**review, "merchant": merchant, "events": list_events(review["id"])}


def attach_many(reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merchants = get_merchants_by_ids([row.get("merchant_id") for row in reviews if row.get("merchant_id")])
    events = list_events_for_reviews([row["id"] for row in reviews])
    attached = []
    for row in reviews:
        attached.append(
            {
                **row,
                "merchant": merchants.get(row.get("merchant_id")),
                "events": events.get(row["id"], []),
            }
        )
    return attached
