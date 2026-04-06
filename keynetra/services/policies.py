"""Policy orchestration service."""

from __future__ import annotations

from keynetra.engine.compiled.decision_graph import COMPILED_POLICY_STORE
from keynetra.engine.compiled.policy_compiler import compile_policy_graph
from keynetra.engine.keynetra_engine import ConditionEvaluator
from keynetra.services.interfaces import (
    DecisionCache,
    PolicyCache,
    PolicyEventPublisher,
    PolicyMutationResult,
    PolicyRepository,
    TenantRepository,
)
from keynetra.services.revisions import RevisionService


class PolicyService:
    """Orchestrates policy persistence and cache invalidation."""

    def __init__(
        self,
        *,
        tenants: TenantRepository,
        policies: PolicyRepository,
        policy_cache: PolicyCache,
        decision_cache: DecisionCache,
        publisher: PolicyEventPublisher,
    ) -> None:
        self._tenants = tenants
        self._policies = policies
        self._policy_cache = policy_cache
        self._decision_cache = decision_cache
        self._publisher = publisher
        self._revisions = RevisionService(tenants)

    def list_policies(self, *, tenant_key: str) -> list[dict[str, object]]:
        tenant = self._tenants.get_or_create(tenant_key)
        data: list[dict[str, object]] = []
        for item in self._policies.list_current_policy_views(tenant_id=tenant.id):
            row = dict(item.__dict__)
            row.pop("state", None)
            data.append(row)
        return data

    def list_policies_page(
        self,
        *,
        tenant_key: str,
        limit: int,
        cursor: dict[str, object] | None,
    ) -> tuple[list[dict[str, object]], str | None]:
        tenant = self._tenants.get_or_create(tenant_key)
        items, next_cursor = self._policies.list_current_policy_page(
            tenant_id=tenant.id, limit=limit, cursor=cursor
        )
        data: list[dict[str, object]] = []
        for item in items:
            row = dict(item.__dict__)
            row.pop("state", None)
            data.append(row)
        return data, next_cursor

    def create_policy(
        self,
        *,
        tenant_key: str,
        policy_key: str,
        action: str,
        effect: str,
        priority: int,
        conditions: dict[str, object],
        created_by: str | None,
        state: str = "active",
    ) -> PolicyMutationResult:
        tenant = self._tenants.get_or_create(tenant_key)
        try:
            result = self._policies.create_policy_version(
                tenant_id=tenant.id,
                policy_key=policy_key,
                action=action,
                effect=effect,
                priority=priority,
                conditions=conditions,
                created_by=created_by,
                state=state,
            )
        except TypeError:
            result = self._policies.create_policy_version(
                tenant_id=tenant.id,
                policy_key=policy_key,
                action=action,
                effect=effect,
                priority=priority,
                conditions=conditions,
                created_by=created_by,
            )
        updated_tenant = self._tenants.bump_policy_version(tenant)
        self._policy_cache.invalidate(updated_tenant.tenant_key)
        self._decision_cache.bump_namespace(updated_tenant.tenant_key)
        self._revisions.bump_revision(tenant_key=updated_tenant.tenant_key)
        COMPILED_POLICY_STORE.invalidate(updated_tenant.tenant_key)
        self._compile_and_store(
            updated_tenant.id, updated_tenant.tenant_key, updated_tenant.policy_version
        )
        self._publisher.publish_policy_update(
            tenant_key=updated_tenant.tenant_key,
            policy_version=updated_tenant.policy_version,
        )
        return result

    def rollback_policy(self, *, tenant_key: str, policy_key: str, version: int) -> tuple[str, int]:
        tenant = self._tenants.get_or_create(tenant_key)
        result = self._policies.rollback_policy(
            tenant_id=tenant.id, policy_key=policy_key, version=version
        )
        updated_tenant = self._tenants.bump_policy_version(tenant)
        self._policy_cache.invalidate(updated_tenant.tenant_key)
        self._decision_cache.bump_namespace(updated_tenant.tenant_key)
        self._revisions.bump_revision(tenant_key=updated_tenant.tenant_key)
        COMPILED_POLICY_STORE.invalidate(updated_tenant.tenant_key)
        self._compile_and_store(
            updated_tenant.id, updated_tenant.tenant_key, updated_tenant.policy_version
        )
        self._publisher.publish_policy_update(
            tenant_key=updated_tenant.tenant_key,
            policy_version=updated_tenant.policy_version,
        )
        return result

    def delete_policy(self, *, tenant_key: str, policy_key: str) -> None:
        tenant = self._tenants.get_or_create(tenant_key)
        self._policies.delete_policy(tenant_id=tenant.id, policy_key=policy_key)
        updated_tenant = self._tenants.bump_policy_version(tenant)
        self._policy_cache.invalidate(updated_tenant.tenant_key)
        self._decision_cache.bump_namespace(updated_tenant.tenant_key)
        self._revisions.bump_revision(tenant_key=updated_tenant.tenant_key)
        COMPILED_POLICY_STORE.invalidate(updated_tenant.tenant_key)
        self._compile_and_store(
            updated_tenant.id, updated_tenant.tenant_key, updated_tenant.policy_version
        )
        self._publisher.publish_policy_update(
            tenant_key=updated_tenant.tenant_key,
            policy_version=updated_tenant.policy_version,
        )

    def _compile_and_store(self, tenant_id: int, tenant_key: str, policy_version: int) -> None:
        policies = self._policies.list_current_policies(tenant_id=tenant_id)
        graph = compile_policy_graph(
            [
                {
                    "action": policy.definition.action,
                    "effect": policy.definition.effect,
                    "priority": policy.definition.priority,
                    "conditions": policy.definition.conditions,
                    "policy_id": policy.definition.policy_id,
                }
                for policy in policies
            ],
            evaluator=ConditionEvaluator(),
            tenant_key=tenant_key,
        )
        COMPILED_POLICY_STORE.set(tenant_key, policy_version, graph)
