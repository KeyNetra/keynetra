from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.config.settings import Settings
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.infrastructure.cache.backends import InMemoryCacheBackend
from keynetra.infrastructure.cache.decision_cache import RedisBackedDecisionCache
from keynetra.infrastructure.cache.policy_cache import RedisBackedPolicyCache
from keynetra.infrastructure.cache.relationship_cache import RedisBackedRelationshipCache
from keynetra.services.authorization import AuthorizationService
from keynetra.services.interfaces import (
    PolicyMutationResult,
    PolicyRecord,
    RelationshipRecord,
    TenantRecord,
)
from keynetra.services.policies import PolicyService
from keynetra.services.relationships import RelationshipService


class FakeTenantRepository:
    def __init__(self) -> None:
        self._tenant = TenantRecord(id=1, tenant_key="default", policy_version=1)

    def get_by_key(self, tenant_key: str) -> TenantRecord | None:
        return self._tenant if tenant_key == self._tenant.tenant_key else None

    def create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        return self._tenant if self._tenant.id == tenant_id else None

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
        self._tenant = TenantRecord(
            id=tenant.id, tenant_key=tenant.tenant_key, policy_version=tenant.policy_version + 1
        )
        return self._tenant

    def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
        return tenant


class FakePolicyRepository:
    def __init__(self) -> None:
        self.list_calls = 0
        self.policies = [
            PolicyRecord(
                id=1,
                definition=PolicyDefinition(
                    action="read",
                    effect="allow",
                    priority=1,
                    policy_id="read:v1",
                    conditions={"role": "admin"},
                ),
            )
        ]

    def list_current_policies(self, *, tenant_id: int) -> list[PolicyRecord]:
        self.list_calls += 1
        return list(self.policies)

    def list_current_policy_views(self, *, tenant_id: int) -> list[Any]:
        raise NotImplementedError

    def create_policy_version(self, **_: Any) -> PolicyMutationResult:
        return PolicyMutationResult(id=1, action="read", effect="allow", priority=1, conditions={})

    def rollback_policy(self, *, tenant_id: int, policy_key: str, version: int) -> tuple[str, int]:
        return policy_key, version


class FakeUserRepository:
    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return {"id": user_id, "role": "admin", "permissions": []}


class FakeRelationshipRepository:
    def __init__(self) -> None:
        self.list_calls = 0

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        self.list_calls += 1
        return [
            RelationshipRecord(
                subject_type=subject_type,
                subject_id=subject_id,
                relation="member_of",
                object_type="team",
                object_id="red",
            )
        ]

    def create(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relation: str,
        object_type: str,
        object_id: str,
    ) -> int:
        return 1


class FakeAuditRepository:
    def write(self, **_: Any) -> None:
        return


@dataclass
class FakePublisher:
    events: list[tuple[str, int]]

    def publish_policy_update(self, *, tenant_key: str, policy_version: int) -> None:
        self.events.append((tenant_key, policy_version))


def test_authorization_service_uses_policy_and_relationship_caches() -> None:
    backend = InMemoryCacheBackend()
    service = AuthorizationService(
        settings=Settings(KEYNETRA_API_KEYS="test"),
        tenants=FakeTenantRepository(),
        policies=FakePolicyRepository(),
        users=FakeUserRepository(),
        relationships=FakeRelationshipRepository(),
        audit=FakeAuditRepository(),
        policy_cache=RedisBackedPolicyCache(backend),
        relationship_cache=RedisBackedRelationshipCache(backend),
        decision_cache=RedisBackedDecisionCache(backend),
    )

    first = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 7},
        action="read",
        resource={},
    )
    second = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 7},
        action="read",
        resource={},
    )

    assert first.decision.allowed is True
    assert second.cached is True
    assert service._policies.list_calls == 1  # type: ignore[attr-defined]
    assert service._relationships.list_calls == 1  # type: ignore[attr-defined]


def test_policy_update_bumps_decision_namespace_and_publishes_event() -> None:
    backend = InMemoryCacheBackend()
    tenants = FakeTenantRepository()
    publisher = FakePublisher(events=[])
    decision_cache = RedisBackedDecisionCache(backend)
    service = PolicyService(
        tenants=tenants,
        policies=FakePolicyRepository(),
        policy_cache=RedisBackedPolicyCache(backend),
        decision_cache=decision_cache,
        publisher=publisher,
    )

    service.create_policy(
        tenant_key="default",
        policy_key="read",
        action="read",
        effect="allow",
        priority=1,
        conditions={},
        created_by="tester",
    )

    assert decision_cache.bump_namespace("default") == 2
    assert publisher.events == [("default", 2)]


def test_relationship_change_invalidates_relationship_cache_and_decisions() -> None:
    backend = InMemoryCacheBackend()
    decision_cache = RedisBackedDecisionCache(backend)
    relationship_cache = RedisBackedRelationshipCache(backend)
    relationship_cache.set(
        tenant_id=1,
        subject_type="user",
        subject_id="7",
        relationships=[
            RelationshipRecord(
                subject_type="user",
                subject_id="7",
                relation="member_of",
                object_type="team",
                object_id="red",
            )
        ],
    )
    service = RelationshipService(
        tenants=FakeTenantRepository(),
        relationships=FakeRelationshipRepository(),
        relationship_cache=relationship_cache,
        decision_cache=decision_cache,
    )

    service.create_relationship(
        tenant_key="default",
        subject_type="user",
        subject_id="7",
        relation="member_of",
        object_type="team",
        object_id="blue",
    )

    assert relationship_cache.get(tenant_id=1, subject_type="user", subject_id="7") is None
    assert decision_cache.bump_namespace("default") == 2
