from __future__ import annotations

from functools import lru_cache
from typing import Any

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency in minimal dev/test envs
    redis = None  # type: ignore[assignment]

from keynetra.config.settings import get_settings


@lru_cache
def get_redis() -> Any | None:
    settings = get_settings()
    if not settings.redis_url or redis is None:
        return None
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
