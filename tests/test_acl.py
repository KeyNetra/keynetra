from __future__ import annotations

from typing import Any

from keynetra.config.settings import Settings
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.infrastructure.cache.access_index_cache import RedisBackedAccessIndexCache
from keynetra.infrastructure.cache.acl_cache import RedisBackedACLCache
from keynetra.infrastructure.cache.backends import InMemoryCacheBackend
from keynetra.infrastructure.cache.decision_cache import RedisBackedDecisionCache
from keynetra.infrastructure.cache.policy_cache import RedisBackedPolicyCache
from keynetra.infrastructure.cache.relationship_cache import RedisBackedRelationshipCache
from keynetra.services.authorization import AuthorizationService
from keynetra.services.interfaces import ACLRecord, PolicyRecord, RelationshipRecord, TenantRecord


class FakeTenantRepository:
    def __init__(self) -> None:
        self._tenant = TenantRecord(id=1, tenant_key="default", policy_version=1)

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        return self._tenant if tenant_id == self._tenant.id else None

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
        self._tenant = TenantRecord(
            id=tenant.id, tenant_key=tenant.tenant_key, policy_version=tenant.policy_version + 1
        )
        return self._tenant


class FakeUserRepository:
    def __init__(
        self, *, roles: list[str] | None = None, permissions: list[str] | None = None
    ) -> None:
        self.roles = roles or ["manager"]
        self.permissions = permissions or []

    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return {"id": user_id, "roles": list(self.roles), "permissions": list(self.permissions)}


class FakePolicyRepository:
    def __init__(self, policies: list[PolicyRecord]) -> None:
        self._policies = policies

    def list_current_policies(self, *, tenant_id: int) -> list[PolicyRecord]:
        return list(self._policies)

    def list_current_policy_views(self, *, tenant_id: int) -> list[Any]:
        return []

    def create_policy_version(self, **_: Any) -> Any:
        raise NotImplementedError

    def rollback_policy(self, *, tenant_id: int, policy_key: str, version: int) -> tuple[str, int]:
        return policy_key, version

    def delete_policy(self, *, tenant_id: int, policy_key: str) -> None:
        return None


class FakeACLRepository:
    def __init__(self, entries: list[ACLRecord]) -> None:
        self.entries = entries
        self.match_calls = 0

    def create_acl_entry(self, **_: Any) -> int:
        raise NotImplementedError

    def list_resource_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str
    ) -> list[ACLRecord]:
        return [
            entry
            for entry in self.entries
            if entry.resource_type == resource_type and entry.resource_id == resource_id
        ]

    def get_acl_entry(self, *, tenant_id: int, acl_id: int) -> ACLRecord | None:
        return next((entry for entry in self.entries if entry.id == acl_id), None)

    def find_matching_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord]:
        self.match_calls += 1
        return [
            entry
            for entry in self.entries
            if entry.resource_type == resource_type
            and entry.resource_id == resource_id
            and entry.action == action
        ]

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None:
        self.entries = [entry for entry in self.entries if entry.id != acl_id]


class FakeRelationshipRepository:
    def __init__(self, relations_by_object: list[RelationshipRecord] | None = None) -> None:
        self.relations_by_object = relations_by_object or []
        self.subject_calls = 0
        self.object_calls = 0

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        self.subject_calls += 1
        return []

    def list_for_subject_page(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        limit: int,
        cursor: dict[str, Any] | None,
    ) -> tuple[list[RelationshipRecord], str | None]:
        return [], None

    def list_for_object(
        self, *, tenant_id: int, object_type: str, object_id: str
    ) -> list[RelationshipRecord]:
        self.object_calls += 1
        return [
            row
            for row in self.relations_by_object
            if row.object_type == object_type and row.object_id == object_id
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
        return None


def _service(
    *,
    policies: list[PolicyRecord],
    acl_entries: list[ACLRecord],
    relations: list[RelationshipRecord] | None = None,
    permissions: list[str] | None = None,
) -> tuple[AuthorizationService, FakeRelationshipRepository, FakeACLRepository]:
    backend = InMemoryCacheBackend()
    relationship_repo = FakeRelationshipRepository(relations)
    acl_repo = FakeACLRepository(acl_entries)
    service = AuthorizationService(
        settings=Settings(KEYNETRA_API_KEYS="test"),
        tenants=FakeTenantRepository(),
        policies=FakePolicyRepository(policies),
        users=FakeUserRepository(permissions=permissions),
        relationships=relationship_repo,
        audit=FakeAuditRepository(),
        policy_cache=RedisBackedPolicyCache(backend),
        relationship_cache=RedisBackedRelationshipCache(backend),
        decision_cache=RedisBackedDecisionCache(backend),
        acl_repository=acl_repo,
        acl_cache=RedisBackedACLCache(backend),
        access_index_cache=RedisBackedAccessIndexCache(backend),
    )
    return service, relationship_repo, acl_repo


def test_acl_allow() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[
            ACLRecord(
                id=1,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="doc123",
                action="read",
                effect="allow",
            )
        ],
    )

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1},
        action="read",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert result.decision.allowed is True
    assert result.decision.policy_id == "acl:1"
    assert any(
        step.step == "acl" and step.outcome == "allow" for step in result.decision.explain_trace
    )


def test_acl_deny() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[
            ACLRecord(
                id=2,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="doc123",
                action="read",
                effect="deny",
            )
        ],
    )

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1},
        action="read",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert result.decision.allowed is False
    assert result.decision.policy_id == "acl:2"
    assert any(
        step.step == "acl" and step.outcome == "deny" for step in result.decision.explain_trace
    )


def test_acl_overrides_rbac_role_permission() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[
            ACLRecord(
                id=3,
                tenant_id=1,
                subject_type="role",
                subject_id="manager",
                resource_type="doc",
                resource_id="doc123",
                action="read",
                effect="deny",
            )
        ],
        permissions=["read"],
    )

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1, "roles": ["manager"]},
        action="read",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert result.decision.allowed is False
    assert result.decision.policy_id == "acl:3"


def test_rbac_fallback_when_no_acl() -> None:
    service, _, _ = _service(policies=[], acl_entries=[], permissions=["approve_payment"])

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1, "roles": ["manager"]},
        action="approve_payment",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert result.decision.allowed is True
    assert result.decision.policy_id == "rbac:role"


def test_abac_still_works_without_acl() -> None:
    policies = [
        PolicyRecord(
            id=1,
            definition=PolicyDefinition(
                action="approve_payment",
                effect="allow",
                priority=10,
                policy_id="policy:v1",
                conditions={"role": "manager", "max_amount": 1000},
            ),
        )
    ]
    service, _, _ = _service(policies=policies, acl_entries=[], permissions=[])

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1, "roles": ["manager"]},
        action="approve_payment",
        resource={"resource_type": "invoice", "resource_id": "inv1", "amount": 100},
    )

    assert result.decision.allowed is True
    assert result.decision.policy_id == "policy:v1"


def test_relationship_based_access() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[],
        relations=[
            RelationshipRecord(
                subject_type="user",
                subject_id="1",
                relation="viewer_of",
                object_type="doc",
                object_id="doc123",
            )
        ],
        permissions=[],
    )

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1},
        action="read",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert result.decision.allowed is True
    assert result.decision.policy_id == "relationship:index"


def test_batch_evaluation_with_acl() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[
            ACLRecord(
                id=1,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="a",
                action="read",
                effect="allow",
            ),
            ACLRecord(
                id=2,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="b",
                action="read",
                effect="deny",
            ),
        ],
    )

    results = service.authorize_batch(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1},
        items=[
            {"action": "read", "resource": {"resource_type": "doc", "resource_id": "a"}},
            {"action": "read", "resource": {"resource_type": "doc", "resource_id": "b"}},
        ],
    )

    assert [result.decision.allowed for result in results] == [True, False]


def test_explain_trace_includes_acl() -> None:
    service, _, _ = _service(
        policies=[],
        acl_entries=[
            ACLRecord(
                id=7,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="doc123",
                action="read",
                effect="allow",
            ),
        ],
    )

    result = service.authorize(
        tenant_key="default",
        principal={"type": "api_key", "id": "test"},
        user={"id": 1},
        action="read",
        resource={"resource_type": "doc", "resource_id": "doc123"},
    )

    assert any("matched ACL entry" in step.detail for step in result.decision.explain_trace)
