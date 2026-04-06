from __future__ import annotations

import json
from typing import Any

from keynetra.config.redis_client import get_redis


def get_cached_user_context(key: str) -> dict[str, Any] | None:
    r = get_redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
    except Exception:
        return None
    return decoded if isinstance(decoded, dict) else None


def set_cached_user_context(key: str, ctx: dict[str, Any], ttl_seconds: int) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(key, max(1, ttl_seconds), json.dumps(ctx, separators=(",", ":"), sort_keys=True))
    except Exception:
        return
