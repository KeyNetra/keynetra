"""Distributed access index cache."""

from __future__ import annotations

import json
from typing import Any

from keynetra.infrastructure.cache.backends import CacheBackend, build_cache_backend
from keynetra.observability.metrics import record_cache_hit, record_cache_miss
from keynetra.services.interfaces import AccessIndexEntry


class RedisBackedAccessIndexCache:
    """Caches resource/action access index entries."""

    def __init__(self, backend: CacheBackend, ttl_seconds: int = 30) -> None:
        self._backend = backend
        self._ttl_seconds = ttl_seconds

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[AccessIndexEntry] | None:
        raw = self._backend.get(
            self._key(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            )
        )
        if raw is None:
            record_cache_miss(cache_type="access_index")
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            record_cache_miss(cache_type="access_index")
            return None
        if not isinstance(payload, list):
            record_cache_miss(cache_type="access_index")
            return None
        record_cache_hit(cache_type="access_index")
        entries: list[AccessIndexEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            allowed_subjects = item.get("allowed_subjects", [])
            if not isinstance(allowed_subjects, list):
                allowed_subjects = []
            entries.append(
                AccessIndexEntry(
                    resource_type=str(item.get("resource_type", resource_type)),
                    resource_id=str(item.get("resource_id", resource_id)),
                    action=str(item.get("action", action)),
                    allowed_subjects=tuple(
                        str(subject) for subject in allowed_subjects if isinstance(subject, str)
                    ),
                    source=str(item.get("source", "unknown")),
                    subject_type=(
                        item.get("subject_type")
                        if item.get("subject_type") is None
                        else str(item.get("subject_type"))
                    ),
                    subject_id=(
                        item.get("subject_id")
                        if item.get("subject_id") is None
                        else str(item.get("subject_id"))
                    ),
                    effect=(
                        item.get("effect")
                        if item.get("effect") is None
                        else str(item.get("effect"))
                    ),
                    acl_id=int(item["acl_id"]) if item.get("acl_id") is not None else None,
                )
            )
        return entries

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        entries: list[AccessIndexEntry],
    ) -> None:
        payload = [
            {
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "action": entry.action,
                "allowed_subjects": list(entry.allowed_subjects),
                "source": entry.source,
                "subject_type": entry.subject_type,
                "subject_id": entry.subject_id,
                "effect": entry.effect,
                "acl_id": entry.acl_id,
            }
            for entry in entries
        ]
        self._backend.set(
            self._key(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            ),
            json.dumps(payload, separators=(",", ":")),
            self._ttl_seconds,
        )

    def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
        self._backend.incr(
            self._namespace_key(
                tenant_id=tenant_id, resource_type=resource_type, resource_id=resource_id
            )
        )

    def invalidate_tenant(self, *, tenant_id: int) -> None:
        self._backend.incr(f"idxns:{tenant_id}:tenant")

    def invalidate_global(self) -> None:
        self._backend.incr("idxns:global")

    def _key(self, *, tenant_id: int, resource_type: str, resource_id: str, action: str) -> str:
        namespace = (
            self._backend.get(
                self._namespace_key(
                    tenant_id=tenant_id, resource_type=resource_type, resource_id=resource_id
                )
            )
            or self._backend.get(f"idxns:{tenant_id}:tenant")
            or self._backend.get("idxns:global")
            or "0"
        )
        return f"idx:{tenant_id}:{namespace}:{resource_type}:{resource_id}:{action}"

    def _namespace_key(self, *, tenant_id: int, resource_type: str, resource_id: str) -> str:
        return f"idxns:{tenant_id}:{resource_type}:{resource_id}"


def build_access_index_cache(redis_client: Any | None) -> RedisBackedAccessIndexCache:
    return RedisBackedAccessIndexCache(build_cache_backend(redis_client))
