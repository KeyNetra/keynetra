from __future__ import annotations

from typing import Any

from keynetra.infrastructure.cache.access_index_cache import RedisBackedAccessIndexCache
from keynetra.infrastructure.cache.acl_cache import RedisBackedACLCache
from keynetra.infrastructure.cache.backends import InMemoryCacheBackend
from keynetra.services.access_indexer import AccessIndexer
from keynetra.services.interfaces import ACLRecord, RelationshipRecord


class FakeACLRepository:
    def __init__(self) -> None:
        self.match_calls = 0

    def create_acl_entry(self, **_: Any) -> int:
        return 1

    def list_resource_acl(self, *, tenant_id: int, resource_type: str, resource_id: str):
        return []

    def get_acl_entry(self, *, tenant_id: int, acl_id: int):
        return None

    def find_matching_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ):
        self.match_calls += 1
        return [
            ACLRecord(
                id=1,
                tenant_id=tenant_id,
                subject_type="user",
                subject_id="7",
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                effect="allow",
            )
        ]

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None:
        return None


class FakeRelationshipRepository:
    def __init__(self) -> None:
        self.object_calls = 0

    def list_for_subject(self, *, tenant_id: int, subject_type: str, subject_id: str):
        return []

    def list_for_subject_page(self, **_: Any):
        return [], None

    def list_for_object(self, *, tenant_id: int, object_type: str, object_id: str):
        self.object_calls += 1
        return [
            RelationshipRecord(
                subject_type="user",
                subject_id="7",
                relation="viewer_of",
                object_type=object_type,
                object_id=object_id,
            )
        ]

    def create(self, **_: Any) -> int:
        return 1


def test_access_index_cache_builds_and_hits() -> None:
    backend = InMemoryCacheBackend()
    acl_repo = FakeACLRepository()
    relationship_repo = FakeRelationshipRepository()
    indexer = AccessIndexer(
        acl_repository=acl_repo,
        acl_cache=RedisBackedACLCache(backend),
        access_index_cache=RedisBackedAccessIndexCache(backend),
        relationships=relationship_repo,
    )

    first = indexer.build_resource_index(
        tenant_id=1,
        resource_type="doc",
        resource_id="doc123",
        action="read",
    )
    second = indexer.build_resource_index(
        tenant_id=1,
        resource_type="doc",
        resource_id="doc123",
        action="read",
    )

    assert len(first) == 2
    assert second == first
    assert acl_repo.match_calls == 1
    assert relationship_repo.object_calls == 1
