"""Policy impact analysis helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.engine.keynetra_engine import AuthorizationInput, KeyNetraEngine
from keynetra.services.interfaces import (
    PolicyRepository,
    RelationshipRepository,
    TenantRepository,
    UserRepository,
)
from keynetra.services.policy_dsl import dsl_to_policy


@dataclass(frozen=True)
class ImpactResult:
    gained_access: list[int]
    lost_access: list[int]


class ImpactAnalyzer:
    def __init__(
        self,
        *,
        tenants: TenantRepository,
        policies: PolicyRepository,
        users: UserRepository,
        relationships: RelationshipRepository,
    ) -> None:
        self._tenants = tenants
        self._policies = policies
        self._users = users
        self._relationships = relationships

    def analyze_policy_change(self, *, tenant_key: str, policy_change: str) -> ImpactResult:
        tenant = self._tenants.get_or_create(tenant_key)
        current_policies = self._policies.list_current_policies(tenant_id=tenant.id)
        changed_policy = dsl_to_policy(policy_change)
        before_engine = KeyNetraEngine([policy.definition for policy in current_policies])
        after_engine = KeyNetraEngine(
            [policy.definition for policy in current_policies]
            + [
                {
                    "action": changed_policy["action"],
                    "effect": changed_policy["effect"],
                    "priority": changed_policy["priority"],
                    "conditions": changed_policy["conditions"],
                    "policy_id": changed_policy["conditions"].get("policy_key"),
                }
            ]
        )

        gained: set[int] = set()
        lost: set[int] = set()
        list_user_ids = getattr(self._users, "list_user_ids", None)
        try:
            user_ids = list_user_ids(tenant_id=tenant.id) if callable(list_user_ids) else []
        except Exception:
            return ImpactResult(gained_access=[], lost_access=[])
        get_user_contexts = getattr(self._users, "get_user_contexts", None)
        try:
            user_contexts = get_user_contexts(user_ids) if callable(get_user_contexts) else {}
        except Exception:
            user_contexts = {}
        list_for_subjects = getattr(self._relationships, "list_for_subjects", None)
        try:
            relationship_map = (
                list_for_subjects(
                    tenant_id=tenant.id,
                    subject_type="user",
                    subject_ids=[str(user_id) for user_id in user_ids],
                )
                if callable(list_for_subjects)
                else {}
            )
        except Exception:
            relationship_map = {}
        for user_id in user_ids:
            try:
                context = (
                    user_contexts.get(user_id)
                    or self._users.get_user_context(user_id)
                    or {
                        "id": user_id,
                        "roles": [],
                        "permissions": [],
                    }
                )
            except Exception:
                context = {"id": user_id, "roles": [], "permissions": []}
            prefetched_relationships = relationship_map.get(str(user_id))
            try:
                user = self._enrich_user_with_relationships(
                    tenant_id=tenant.id,
                    user=context,
                    prefetched_relationships=prefetched_relationships,
                )
                candidate_resources = self._candidate_resources(
                    tenant_id=tenant.id, user_id=user_id
                )
            except Exception:
                continue
            for resource in candidate_resources:
                before = before_engine.decide(
                    AuthorizationInput(
                        user=user, action=changed_policy["action"], resource=resource
                    )
                )
                after = after_engine.decide(
                    AuthorizationInput(
                        user=user, action=changed_policy["action"], resource=resource
                    )
                )
                if not before.allowed and after.allowed:
                    gained.add(user_id)
                if before.allowed and not after.allowed:
                    lost.add(user_id)
        return ImpactResult(gained_access=sorted(gained), lost_access=sorted(lost))

    def _candidate_resources(self, *, tenant_id: int, user_id: int) -> list[dict[str, Any]]:
        resources: list[dict[str, Any]] = [
            {"resource_type": "document", "resource_id": f"user-{user_id}", "owner_id": user_id}
        ]
        relationships = self._relationships.list_for_subject(
            tenant_id=tenant_id, subject_type="user", subject_id=str(user_id)
        )
        for relation in relationships:
            resources.append(
                {
                    "resource_type": relation.object_type,
                    "resource_id": relation.object_id,
                    "owner_id": user_id,
                }
            )
        return resources

    def _enrich_user_with_relationships(
        self,
        *,
        tenant_id: int,
        user: dict[str, Any],
        prefetched_relationships: list[Any] | None = None,
    ) -> dict[str, Any]:
        enriched = dict(user)
        user_id = enriched.get("id")
        if isinstance(user_id, int):
            if prefetched_relationships is not None:
                enriched["relations"] = [
                    relation.to_dict() for relation in prefetched_relationships
                ]
                return enriched
            enriched["relations"] = [
                relation.to_dict()
                for relation in self._relationships.list_for_subject(
                    tenant_id=tenant_id, subject_type="user", subject_id=str(user_id)
                )
            ]
        return enriched
