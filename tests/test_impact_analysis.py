from __future__ import annotations

from typing import Any

from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.services.impact_analysis import ImpactAnalyzer
from keynetra.services.interfaces import PolicyRecord, RelationshipRecord, TenantRecord


class FakeTenantRepository:
    def __init__(self) -> None:
        self._tenant = TenantRecord(id=1, tenant_key="default", policy_version=1, revision=1)

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        return self._tenant

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        return self._tenant if tenant_id == self._tenant.id else None

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
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
    def __init__(self, user_ids: list[int], contexts: dict[int, dict[str, Any]]) -> None:
        self._user_ids = list(user_ids)
        self._contexts = dict(contexts)

    def list_user_ids(self, *, tenant_id: int) -> list[int]:
        return list(self._user_ids)

    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        return self._contexts.get(user_id)


class FakeRelationshipRepository:
    def __init__(self, relationships: list[RelationshipRecord]) -> None:
        self._relationships = list(relationships)

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        return [
            row
            for row in self._relationships
            if row.subject_type == subject_type and row.subject_id == subject_id
        ]

    def list_for_subject_page(self, **_: Any):
        return [], None

    def list_for_object(
        self, *, tenant_id: int, object_type: str, object_id: str
    ) -> list[RelationshipRecord]:
        return [
            row
            for row in self._relationships
            if row.object_type == object_type and row.object_id == object_id
        ]

    def create(self, **_: Any) -> int:
        return 1


def test_policy_change_gains_access_for_matching_users() -> None:
    analyzer = ImpactAnalyzer(
        tenants=FakeTenantRepository(),
        policies=FakePolicyRepository([]),
        users=FakeUserRepository(
            user_ids=[1, 2],
            contexts={
                1: {"id": 1, "role": "admin", "roles": ["admin"], "permissions": []},
                2: {"id": 2, "role": "viewer", "roles": ["viewer"], "permissions": []},
            },
        ),
        relationships=FakeRelationshipRepository([]),
    )

    result = analyzer.analyze_policy_change(
        tenant_key="default",
        policy_change="""
allow:
  action: share_document
  priority: 10
  policy_key: share-admin
  when:
    role: admin
""",
    )

    assert result.gained_access == [1]
    assert result.lost_access == []


def test_policy_change_can_remove_access() -> None:
    analyzer = ImpactAnalyzer(
        tenants=FakeTenantRepository(),
        policies=FakePolicyRepository(
            [
                PolicyRecord(
                    id=1,
                    definition=PolicyDefinition(
                        action="share_document",
                        effect="allow",
                        priority=10,
                        policy_id="share-admin",
                        conditions={"role": "admin"},
                    ),
                )
            ]
        ),
        users=FakeUserRepository(
            user_ids=[1, 2],
            contexts={
                1: {"id": 1, "role": "admin", "roles": ["admin"], "permissions": []},
                2: {"id": 2, "role": "viewer", "roles": ["viewer"], "permissions": []},
            },
        ),
        relationships=FakeRelationshipRepository([]),
    )

    result = analyzer.analyze_policy_change(
        tenant_key="default",
        policy_change="""
deny:
  action: share_document
  priority: 1
  policy_key: share-admin-deny
  when:
    role: admin
""",
    )

    assert result.gained_access == []
    assert result.lost_access == [1]
