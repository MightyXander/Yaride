"""Кэш Redis (этап 2): opt-in через REDIS_URL; без URL — no-op."""

from __future__ import annotations

import json
import os
from typing import Any

_redis_client: Any | None = None
_redis_checked = False

CATALOG_TTL_S = 600
TRIPS_SEARCH_TTL_S = 45


def redis_enabled() -> bool:
    return bool(os.getenv("REDIS_URL", "").strip())


def _client() -> Any | None:
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis

        _redis_client = redis.Redis.from_url(url, decode_responses=True)
        _redis_client.ping()
    except Exception:
        _redis_client = None
    return _redis_client


def cache_get(key: str) -> Any | None:
    client = _client()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def cache_set(key: str, value: Any, *, ttl_s: int = 300) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.setex(key, ttl_s, json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return


def cache_delete(key: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        return


def cache_invalidate_prefix(prefix: str) -> None:
    """Удалить все ключи с заданным префиксом (инвалидация поиска поездок)."""
    client = _client()
    if client is None:
        return
    try:
        for key in client.scan_iter(match=f"{prefix}*", count=100):
            client.delete(key)
    except Exception:
        return


def invalidate_trip_search_cache() -> None:
    cache_invalidate_prefix("trips:search:")
