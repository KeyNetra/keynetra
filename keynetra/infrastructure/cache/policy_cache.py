"""Policy cache adapter.

Infrastructure stores serialized policy definitions. Services remain
responsible for constructing the engine from cached policy records.
"""

from __future__ import annotations

import json
from typing import Any

from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.infrastructure.cache.backends import CacheBackend, build_cache_backend
from keynetra.services.interfaces import PolicyRecord


class RedisBackedPolicyCache:
    """Policy cache with per-tenant namespace invalidation."""

    def __init__(self, backend: CacheBackend) -> None:
        self._backend = backend

    def get(self, tenant_key: str, policy_version: int) -> list[PolicyRecord] | None:
        key = self._cache_key(tenant_key, policy_version)
        raw = self._backend.get(key)
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, list):
            return None
        records: list[PolicyRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            records.append(
                PolicyRecord(
                    id=int(item["id"]),
                    definition=PolicyDefinition.from_dict(item["definition"]),
                )
            )
        return records

    def set(self, tenant_key: str, policy_version: int, policies: list[PolicyRecord]) -> None:
        key = self._cache_key(tenant_key, policy_version)
        payload = [
            {
                "id": policy.id,
                "definition": {
                    "action": policy.definition.action,
                    "effect": policy.definition.effect,
                    "priority": policy.definition.priority,
                    "conditions": policy.definition.conditions,
                    "policy_id": policy.definition.policy_id,
                },
            }
            for policy in policies
        ]
        self._backend.set(key, json.dumps(payload, separators=(",", ":")))

    def invalidate(self, tenant_key: str) -> None:
        self._backend.incr(self._namespace_key(tenant_key))

    def _cache_key(self, tenant_key: str, policy_version: int) -> str:
        namespace = self._backend.get(self._namespace_key(tenant_key)) or "0"
        return f"pol:{tenant_key}:{namespace}:{policy_version}"

    def _namespace_key(self, tenant_key: str) -> str:
        return f"polns:{tenant_key}"


def build_policy_cache(redis_client: Any | None) -> RedisBackedPolicyCache:
    """Build the default policy cache."""

    return RedisBackedPolicyCache(build_cache_backend(redis_client))
