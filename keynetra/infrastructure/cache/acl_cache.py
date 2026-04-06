"""ACL cache adapter."""

from __future__ import annotations

import json
from typing import Any

from keynetra.infrastructure.cache.backends import CacheBackend, build_cache_backend
from keynetra.observability.metrics import record_cache_hit, record_cache_miss
from keynetra.services.interfaces import ACLRecord


class RedisBackedACLCache:
    """Caches ACL lists per tenant resource/action."""

    def __init__(self, backend: CacheBackend, ttl_seconds: int = 30) -> None:
        self._backend = backend
        self._ttl_seconds = ttl_seconds

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord] | None:
        raw = self._backend.get(
            self._key(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            )
        )
        if raw is None:
            record_cache_miss(cache_type="acl")
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            record_cache_miss(cache_type="acl")
            return None
        if not isinstance(payload, list):
            record_cache_miss(cache_type="acl")
            return None
        record_cache_hit(cache_type="acl")
        records: list[ACLRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            records.append(
                ACLRecord(
                    id=int(item.get("id", 0)),
                    tenant_id=int(item.get("tenant_id", tenant_id)),
                    subject_type=str(item.get("subject_type", "")),
                    subject_id=str(item.get("subject_id", "")),
                    resource_type=str(item.get("resource_type", resource_type)),
                    resource_id=str(item.get("resource_id", resource_id)),
                    action=str(item.get("action", action)),
                    effect=str(item.get("effect", "deny")),
                    created_at=item.get("created_at"),
                )
            )
        return records

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        acl_entries: list[ACLRecord],
    ) -> None:
        payload = [entry.to_dict() for entry in acl_entries]
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

    def invalidate_global(self) -> None:
        self._backend.incr("aclns:global")

    def _key(self, *, tenant_id: int, resource_type: str, resource_id: str, action: str) -> str:
        namespace = (
            self._backend.get(
                self._namespace_key(
                    tenant_id=tenant_id, resource_type=resource_type, resource_id=resource_id
                )
            )
            or self._backend.get("aclns:global")
            or "0"
        )
        return f"acl:{tenant_id}:{namespace}:{resource_type}:{resource_id}:{action}"

    def _namespace_key(self, *, tenant_id: int, resource_type: str, resource_id: str) -> str:
        return f"aclns:{tenant_id}:{resource_type}:{resource_id}"


def build_acl_cache(redis_client: Any | None) -> RedisBackedACLCache:
    return RedisBackedACLCache(build_cache_backend(redis_client))
