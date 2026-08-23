from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings

_tables_ready: bool | None = None
_probed_at: float = 0.0
_TRUE_TTL = 60.0
_FALSE_TTL = 8.0


def _headers() -> dict[str, str]:
    settings = get_settings()
    key = settings.supabase_server_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest(path: str) -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/rest/v1/{path.lstrip('/')}"


def sb_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    headers = _headers()
    if extra_headers:
        headers.update(extra_headers)
    with httpx.Client(timeout=20.0) as client:
        response = client.request(
            method,
            _rest(path),
            params=params,
            json=json,
            headers=headers,
        )
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()


def probe_tables(*, force: bool = False) -> bool:
    """Retry when tables were missing so applying schema.sql does not require a restart."""
    global _tables_ready, _probed_at
    now = time.monotonic()
    if not force and _tables_ready is True and now - _probed_at < _TRUE_TTL:
        return True
    if not force and _tables_ready is False and now - _probed_at < _FALSE_TTL:
        return False
    try:
        sb_request("GET", "merchants", params={"select": "id", "limit": "1"})
        sb_request("GET", "reviews", params={"select": "id", "limit": "1"})
        sb_request("GET", "review_events", params={"select": "id", "limit": "1"})
        _tables_ready = True
    except Exception:
        _tables_ready = False
    _probed_at = now
    return _tables_ready


def reset_table_probe() -> None:
    global _tables_ready, _probed_at
    _tables_ready = None
    _probed_at = 0.0
