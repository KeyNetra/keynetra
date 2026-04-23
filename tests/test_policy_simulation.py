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
from keynetra.services.policy_simulator import PolicySimulator


class FakeTenantRepository:
    def __init__(self) -> None:
        self._tenant = TenantRecord(id=1, tenant_key="default", policy_version=1, revision=1)

    def get_by_key(self, tenant_key: str) -> TenantRecord | None:
        return self._tenant if tenant_key == self._tenant.tenant_key else None

    def create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        return self._tenant if tenant_id == self._tenant.id else None

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
        self._tenant = TenantRecord(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version + 1,
            revision=tenant.revision,
        )
        return self._tenant

    def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
        self._tenant = TenantRecord(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version,
            revision=tenant.revision + 1,
        )
        return self._tenant


class FakePolicyRepository:
    def __init__(self, policies: list[PolicyRecord]) -> None:
        self._policies = list(policies)

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


class FakeUserRepository:
    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return {"id": user_id, "role": "admin", "roles": ["admin"], "permissions": []}


class FakeRelationshipRepository:
    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        return []

    def list_for_subject_page(self, **_: Any):
        return [], None

    def list_for_object(
        self, *, tenant_id: int, object_type: str, object_id: str
    ) -> list[RelationshipRecord]:
        return []

    def create(self, **_: Any) -> int:
        return 1


class FakeACLRepository:
    def create_acl_entry(self, **_: Any) -> int:
        return 1

    def list_resource_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str
    ) -> list[ACLRecord]:
        return []

    def get_acl_entry(self, *, tenant_id: int, acl_id: int) -> ACLRecord | None:
        return None

    def find_matching_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord]:
        return []

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None:
        return None


class FakeAuditRepository:
    def write(self, **_: Any) -> None:
        return None


def _authorization_service(
    tenants: FakeTenantRepository, policies: FakePolicyRepository
) -> AuthorizationService:
    backend = InMemoryCacheBackend()
    return AuthorizationService(
        settings=Settings(KEYNETRA_API_KEYS="test", KEYNETRA_POLICIES_JSON="[]"),
        tenants=tenants,
        policies=policies,
        users=FakeUserRepository(),
        relationships=FakeRelationshipRepository(),
        audit=FakeAuditRepository(),
        policy_cache=RedisBackedPolicyCache(backend),
        relationship_cache=RedisBackedRelationshipCache(backend),
        decision_cache=RedisBackedDecisionCache(backend),
        acl_repository=FakeACLRepository(),
        acl_cache=RedisBackedACLCache(backend),
        access_index_cache=RedisBackedAccessIndexCache(backend),
    )


def test_policy_simulator_reports_before_and_after() -> None:
    tenants = FakeTenantRepository()
    policies = FakePolicyRepository(
        [
            PolicyRecord(
                id=1,
                definition=PolicyDefinition(
                    action="share_document",
                    effect="deny",
                    priority=10,
                    policy_id="share-admin-deny:v1",
                    conditions={"role": "admin"},
                ),
            )
        ]
    )
    simulator = PolicySimulator(
        tenants=tenants,
        policies=policies,
        authorization_service=_authorization_service(tenants, policies),
    )

    result = simulator.simulate_policy_change(
        tenant_key="default",
        user={"id": 1, "role": "admin", "roles": ["admin"]},
        action="share_document",
        resource={"resource_type": "document", "resource_id": "doc-1"},
        context={},
        policy_change="""
allow:
  action: share_document
  priority: 1
  policy_key: share-admin
  when:
    role: admin
""",
    )

    assert result.decision_before.decision == "deny"
    assert result.decision_after.decision == "allow"
    assert result.decision_after.policy_id == "share-admin"
