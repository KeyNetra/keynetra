"""Relationship cache adapter."""

from __future__ import annotations

import json
from typing import Any

from keynetra.infrastructure.cache.backends import CacheBackend, build_cache_backend
from keynetra.services.interfaces import RelationshipRecord


class RedisBackedRelationshipCache:
    """Caches relationship lists per tenant subject."""

    def __init__(self, backend: CacheBackend, ttl_seconds: int = 30) -> None:
        self._backend = backend
        self._ttl_seconds = ttl_seconds

    def get(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord] | None:
        raw = self._backend.get(
            self._key(tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id)
        )
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, list):
            return None
        relationships: list[RelationshipRecord] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            relationships.append(
                RelationshipRecord(
                    subject_type=str(item.get("subject_type", "")),
                    subject_id=str(item.get("subject_id", "")),
                    relation=str(item.get("relation", "")),
                    object_type=str(item.get("object_type", "")),
                    object_id=str(item.get("object_id", "")),
                )
            )
        return relationships

    def set(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relationships: list[RelationshipRecord],
    ) -> None:
        payload = [relationship.to_dict() for relationship in relationships]
        self._backend.set(
            self._key(tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id),
            json.dumps(payload, separators=(",", ":")),
            self._ttl_seconds,
        )

    def invalidate(self, *, tenant_id: int, subject_type: str, subject_id: str) -> None:
        self._backend.delete(
            self._key(tenant_id=tenant_id, subject_type=subject_type, subject_id=subject_id)
        )

    def _key(self, *, tenant_id: int, subject_type: str, subject_id: str) -> str:
        return f"rel:{tenant_id}:{subject_type}:{subject_id}"


def build_relationship_cache(redis_client: Any | None) -> RedisBackedRelationshipCache:
    """Build the default relationship cache."""

    return RedisBackedRelationshipCache(build_cache_backend(redis_client))
