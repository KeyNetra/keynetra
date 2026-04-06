"""Service-layer contracts.

Services orchestrate authorization flows against these interfaces. Concrete
database, cache, and external integrations belong in infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from keynetra.engine.keynetra_engine import (
    AuthorizationDecision,
    AuthorizationInput,
    PolicyDefinition,
)


@dataclass(frozen=True)
class TenantRecord:
    """Tenant data needed by orchestration services."""

    id: int
    tenant_key: str
    policy_version: int
    revision: int = 1


@dataclass(frozen=True)
class RelationshipRecord:
    """Explicit relationship edge supplied to the engine as input."""

    subject_type: str
    subject_id: str
    relation: str
    object_type: str
    object_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "relation": self.relation,
            "object_type": self.object_type,
            "object_id": self.object_id,
        }


@dataclass(frozen=True)
class ACLRecord:
    """Explicit resource ACL row supplied to the engine."""

    id: int
    tenant_id: int
    subject_type: str
    subject_id: str
    resource_type: str
    resource_id: str
    action: str
    effect: str
    created_at: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "effect": self.effect,
            "created_at": (
                self.created_at.isoformat()
                if hasattr(self.created_at, "isoformat")
                else self.created_at
            ),
        }


@dataclass(frozen=True)
class PolicyRecord:
    """Policy data loaded from persistence for engine evaluation."""

    id: int
    definition: PolicyDefinition


@dataclass(frozen=True)
class PolicyMutationResult:
    """Service-facing result for policy writes."""

    id: int
    action: str
    effect: str
    priority: int
    conditions: dict[str, Any] = field(default_factory=dict)
    state: str = "active"


@dataclass(frozen=True)
class PolicyListItem:
    """Projected policy data for API reads."""

    id: int
    action: str
    effect: str
    priority: int
    conditions: dict[str, Any] = field(default_factory=dict)
    state: str = "active"


@dataclass(frozen=True)
class AuditListItem:
    id: int
    principal_type: str
    principal_id: str
    correlation_id: str | None
    user: dict[str, Any]
    action: str
    resource: dict[str, Any]
    decision: str
    matched_policies: list[Any]
    reason: str | None
    evaluated_rules: list[Any]
    failed_conditions: list[Any]
    created_at: Any


@dataclass(frozen=True)
class AuthModelRecord:
    """Stored authorization model for a tenant."""

    id: int
    tenant_id: int
    schema_text: str
    schema_json: dict[str, Any]
    compiled_json: dict[str, Any]
    created_at: Any | None = None
    updated_at: Any | None = None


@dataclass(frozen=True)
class CachedDecision:
    """Cached authorization response owned by infrastructure."""

    allowed: bool
    decision: str
    reason: str | None
    policy_id: str | None
    matched_policies: list[str] = field(default_factory=list)
    explain_trace: list[dict[str, Any]] = field(default_factory=list)
    failed_conditions: list[str] = field(default_factory=list)

    @classmethod
    def from_decision(cls, decision: AuthorizationDecision) -> CachedDecision:
        return cls(
            allowed=decision.allowed,
            decision=decision.decision,
            reason=decision.reason,
            policy_id=decision.policy_id,
            matched_policies=list(decision.matched_policies),
            explain_trace=[step.to_dict() for step in decision.explain_trace],
            failed_conditions=list(decision.failed_conditions),
        )


class TenantRepository(Protocol):
    """Persistence boundary for tenant data."""

    def get_or_create(self, tenant_key: str) -> TenantRecord: ...

    def get_by_id(self, tenant_id: int) -> TenantRecord | None: ...

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord: ...

    def bump_revision(self, tenant: TenantRecord) -> TenantRecord: ...


class PolicyRepository(Protocol):
    """Persistence boundary for policy storage."""

    def list_current_policies(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[PolicyRecord]: ...

    def list_current_policy_views(self, *, tenant_id: int) -> list[PolicyListItem]: ...

    def list_current_policy_page(
        self,
        *,
        tenant_id: int,
        limit: int,
        cursor: dict[str, Any] | None,
    ) -> tuple[list[PolicyListItem], str | None]: ...

    def create_policy_version(
        self,
        *,
        tenant_id: int,
        policy_key: str,
        action: str,
        effect: str,
        priority: int,
        conditions: dict[str, Any],
        created_by: str | None,
        state: str = "active",
    ) -> PolicyMutationResult: ...

    def rollback_policy(
        self, *, tenant_id: int, policy_key: str, version: int
    ) -> tuple[str, int]: ...

    def delete_policy(self, *, tenant_id: int, policy_key: str) -> None: ...


class AuthModelRepository(Protocol):
    """Persistence boundary for authorization modeling schemas."""

    def get_model(self, *, tenant_id: int) -> AuthModelRecord | None: ...

    def upsert_model(
        self,
        *,
        tenant_id: int,
        schema_text: str,
        schema_json: dict[str, Any],
        compiled_json: dict[str, Any],
    ) -> AuthModelRecord: ...


class UserRepository(Protocol):
    """Persistence boundary for user context lookup."""

    def get_user_context(self, user_id: int) -> dict[str, Any] | None: ...

    def list_user_ids(self, *, tenant_id: int) -> list[int]: ...


class RelationshipRepository(Protocol):
    """Persistence boundary for relationship lookup and writes."""

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]: ...

    def list_for_subject_page(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        limit: int,
        cursor: dict[str, Any] | None,
    ) -> tuple[list[RelationshipRecord], str | None]: ...

    def list_for_object(
        self,
        *,
        tenant_id: int,
        object_type: str,
        object_id: str,
    ) -> list[RelationshipRecord]: ...

    def create(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relation: str,
        object_type: str,
        object_id: str,
    ) -> int: ...


class AuditRepository(Protocol):
    """Persistence boundary for audit writes."""

    def write(
        self,
        *,
        tenant_id: int,
        principal_type: str,
        principal_id: str,
        authorization_input: AuthorizationInput,
        decision: AuthorizationDecision,
        correlation_id: str | None = None,
    ) -> None: ...

    def list_page(
        self,
        *,
        tenant_id: int,
        limit: int,
        cursor: dict[str, Any] | None,
        user_id: str | None,
        resource_id: str | None,
        decision: str | None,
        start_time: Any | None,
        end_time: Any | None,
    ) -> tuple[list[AuditListItem], str | None]: ...


class PolicyCache(Protocol):
    """Cache boundary for policy definitions."""

    def get(self, tenant_key: str, policy_version: int) -> list[PolicyRecord] | None: ...

    def set(self, tenant_key: str, policy_version: int, policies: list[PolicyRecord]) -> None: ...

    def invalidate(self, tenant_key: str) -> None: ...


class RelationshipCache(Protocol):
    """Cache boundary for relationship lookups."""

    def get(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord] | None: ...

    def set(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relationships: list[RelationshipRecord],
    ) -> None: ...


class ACLRepository(Protocol):
    """Persistence boundary for ACL lookup and writes."""

    def create_acl_entry(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        effect: str,
    ) -> int: ...

    def list_resource_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str
    ) -> list[ACLRecord]: ...

    def get_acl_entry(self, *, tenant_id: int, acl_id: int) -> ACLRecord | None: ...

    def find_matching_acl(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> list[ACLRecord]: ...

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None: ...


class ACLCache(Protocol):
    """Cache boundary for ACL lookups."""

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[ACLRecord] | None: ...

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        acl_entries: list[ACLRecord],
    ) -> None: ...

    def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None: ...


@dataclass(frozen=True)
class AccessIndexEntry:
    """Cached access index entry for resource/action lookup."""

    resource_type: str
    resource_id: str
    action: str
    allowed_subjects: tuple[str, ...]
    source: str
    subject_type: str | None = None
    subject_id: str | None = None
    effect: str | None = None
    acl_id: int | None = None


class AccessIndexCache(Protocol):
    """Cache boundary for distributed access indexing."""

    def get(
        self, *, tenant_id: int, resource_type: str, resource_id: str, action: str
    ) -> list[AccessIndexEntry] | None: ...

    def set(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        entries: list[AccessIndexEntry],
    ) -> None: ...

    def invalidate(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None: ...

    def invalidate_tenant(self, *, tenant_id: int) -> None: ...

    def invalidate_global(self) -> None: ...


class RoleBindingRepository(Protocol):
    """Optional persistence boundary for role binding state changes."""

    def list_user_ids(self, *, tenant_id: int) -> list[int]: ...

    def invalidate(self, *, tenant_id: int, subject_type: str, subject_id: str) -> None: ...


class DecisionCache(Protocol):
    """Cache boundary for authorization decisions."""

    def get(self, key: str) -> CachedDecision | None: ...

    def set(self, key: str, value: CachedDecision, ttl_seconds: int) -> None: ...

    def make_key(
        self,
        *,
        tenant_key: str,
        policy_version: int,
        authorization_input: AuthorizationInput,
        revision: int | None = None,
    ) -> str: ...

    def bump_namespace(self, tenant_key: str) -> int: ...


class PolicyEventPublisher(Protocol):
    """External system boundary for policy invalidation fanout."""

    def publish_policy_update(self, *, tenant_key: str, policy_version: int) -> None: ...
