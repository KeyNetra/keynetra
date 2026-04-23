from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass
class _CacheItem(Generic[V]):
    value: V
    expires_at: float | None


class ThreadSafeTTLCache(Generic[K, V]):
    """Small bounded TTL cache for hot-path in-process lookups."""

    def __init__(
        self,
        *,
        max_entries: int,
        default_ttl_seconds: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._max_entries = max(1, max_entries)
        self._default_ttl_seconds = default_ttl_seconds
        self._items: OrderedDict[K, _CacheItem[V]] = OrderedDict()
        self._lock = RLock()
        self._clock = clock or time.monotonic

    def get(self, key: K) -> V | None:
        with self._lock:
            self._purge_expired_locked()
            item = self._items.get(key)
            if item is None:
                return None
            if item.expires_at is not None and item.expires_at <= self._clock():
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return item.value

    def set(self, key: K, value: V, ttl_seconds: float | None = None) -> None:
        expires_at = self._expires_at(ttl_seconds)
        with self._lock:
            self._purge_expired_locked()
            self._items[key] = _CacheItem(value=value, expires_at=expires_at)
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)

    def delete(self, key: K) -> None:
        with self._lock:
            self._items.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def get_with_expiry(self, key: K) -> tuple[V, float | None] | None:
        with self._lock:
            self._purge_expired_locked()
            item = self._items.get(key)
            if item is None:
                return None
            if item.expires_at is not None and item.expires_at <= self._clock():
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return item.value, item.expires_at

    def _expires_at(self, ttl_seconds: float | None) -> float | None:
        effective_ttl = self._default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if effective_ttl is None:
            return None
        return self._clock() + max(0.001, float(effective_ttl))

    def _purge_expired_locked(self) -> None:
        now = self._clock()
        expired = [
            key
            for key, item in self._items.items()
            if item.expires_at is not None and item.expires_at <= now
        ]
        for key in expired:
            self._items.pop(key, None)
