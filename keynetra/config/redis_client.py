from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any

from keynetra.config.settings import get_settings


@lru_cache
def get_redis() -> Any | None:
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        redis_module = import_module("redis")
    except ModuleNotFoundError:  # pragma: no cover - optional dependency in minimal dev/test envs
        return None
    return redis_module.Redis.from_url(settings.redis_url, decode_responses=True)
