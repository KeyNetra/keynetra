"""Cache backend implementations.

Infrastructure owns cache transport details. Services use cache interfaces
defined in ``keynetra.services.interfaces``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from keynetra.infrastructure.logging import log_event

_logger = logging.getLogger("keynetra.cache")

class CacheBackend(Protocol):
    """Minimal key/value backend required by cache adapters."""

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def incr(self, key: str) -> int: ...


class InMemoryCacheBackend:
    """Simple in-memory TTL cache used when Redis is unavailable."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[str, float | None]] = {}

    def get(self, key: str) -> str | None:
        item = self._values.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and expires_at <= time.time():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        expires_at = None if ttl_seconds is None else time.time() + max(1, ttl_seconds)
        self._values[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._values.pop(key, None)

    def incr(self, key: str) -> int:
        current = self.get(key)
        next_value = (int(current) if current is not None else 0) + 1
        self.set(key, str(next_value))
        return next_value


class RedisCacheBackend:
    """Redis-backed cache wrapper with the same minimal surface."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        try:
            value = self._client.get(key)
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            log_event(_logger, event="cache_backend_get_failed", key=key, reason=repr(exc))
            return None
        if value is None:
            return None
        return str(value)

    def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        try:
            if ttl_seconds is None:
                self._client.set(key, value)
            else:
                self._client.setex(key, max(1, ttl_seconds), value)
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            log_event(_logger, event="cache_backend_set_failed", key=key, reason=repr(exc))
            return

    def delete(self, key: str) -> None:
        try:
            self._client.delete(key)
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            log_event(_logger, event="cache_backend_delete_failed", key=key, reason=repr(exc))
            return

    def incr(self, key: str) -> int:
        try:
            return int(self._client.incr(key))
        except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
            log_event(_logger, event="cache_backend_incr_failed", key=key, reason=repr(exc))
            return 0


_memory_backend = InMemoryCacheBackend()


def build_cache_backend(client: Any | None) -> CacheBackend:
    """Return a Redis backend when available, otherwise the shared memory fallback."""

    if client is None:
        return _memory_backend
    return RedisCacheBackend(client)
