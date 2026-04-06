from __future__ import annotations

import json
import logging
from typing import Any

from keynetra.config.redis_client import get_redis
from keynetra.infrastructure.logging import log_event
from keynetra.infrastructure.metrics import record_cache_event

_logger = logging.getLogger("keynetra.cache.user")


def get_cached_user_context(key: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
    except (ConnectionError, RuntimeError, ValueError, TypeError) as exc:
        record_cache_event(cache_name="relationship", outcome="fallback")
        log_event(
            _logger,
            event="user_cache_fetch_failed",
            key=key,
            reason=repr(exc),
        )
        return None
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except (TypeError, ValueError) as exc:
        log_event(
            _logger,
            event="user_cache_decode_failed",
            key=key,
            reason=repr(exc),
        )
        return None
    return decoded if isinstance(decoded, dict) else None


def set_cached_user_context(key: str, ctx: dict[str, Any], ttl_seconds: int) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(key, max(1, ttl_seconds), json.dumps(ctx, separators=(",", ":"), sort_keys=True))
    except (ConnectionError, RuntimeError, ValueError, TypeError) as exc:
        record_cache_event(cache_name="relationship", outcome="fallback")
        log_event(
            _logger,
            event="user_cache_store_failed",
            key=key,
            reason=repr(exc),
        )
        return
