"""Policy and access simulation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.engine.keynetra_engine import AuthorizationDecision, KeyNetraEngine
from keynetra.services.authorization import AuthorizationService
from keynetra.services.errors import TenantNotFoundError
from keynetra.services.interfaces import PolicyRepository, TenantRepository
from keynetra.services.policy_dsl import dsl_to_policy


@dataclass(frozen=True)
class SimulationResult:
    decision_before: AuthorizationDecision
    decision_after: AuthorizationDecision


class PolicySimulator:
    def __init__(
        self,
        *,
        tenants: TenantRepository,
        policies: PolicyRepository,
        authorization_service: AuthorizationService,
    ) -> None:
        self._tenants = tenants
        self._policies = policies
        self._authorization_service = authorization_service

    def simulate_policy_change(
        self,
        *,
        tenant_key: str,
        user: dict[str, Any],
        action: str,
        resource: dict[str, Any],
        context: dict[str, Any],
        policy_change: str,
    ) -> SimulationResult:
        tenant = self._tenants.get_by_key(tenant_key)
        if tenant is None:
            raise TenantNotFoundError(tenant_key)
        authorization_input, _ = self._authorization_service._build_input(
            tenant_key=tenant_key,
            user=user,
            action=action,
            resource=resource,
            context=context,
        )
        before = self._authorization_service.authorize(
            tenant_key=tenant_key,
            principal={"type": "simulator", "id": "simulator"},
            user=user,
            action=action,
            resource=resource,
            context=context,
            audit=False,
        ).decision

        changed_policy = dsl_to_policy(policy_change)
        current_policies = self._policies.list_current_policies(tenant_id=tenant.id)
        engine = KeyNetraEngine(
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
        after = engine.decide(authorization_input)
        return SimulationResult(decision_before=before, decision_after=after)
