"""Policy linting heuristics for pre-flight warnings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from keynetra.domain.models.rbac import Role
from keynetra.services.interfaces import PolicyRepository


@dataclass(frozen=True)
class PolicyLintWarning:
    message: str


class PolicyLintService:
    """Heuristics for unused roles and duplicate/conflicting rules."""

    def __init__(self, *, session: Session, policies: PolicyRepository) -> None:
        self._session = session
        self._policies = policies

    def lint(self, *, tenant_id: int) -> list[str]:
        warnings: list[str] = []
        role_names = {name for name in self._session.execute(select(Role.name)).scalars().all()}
        policy_views = self._policies.list_current_policy_views(tenant_id=tenant_id)

        self._collect_unused_role_warnings(role_names, policy_views, warnings)
        self._collect_duplicate_warnings(policy_views, warnings)
        return warnings

    @staticmethod
    def _serialize_conditions(conditions: dict[str, Any]) -> str:
        clean = {k: v for k, v in conditions.items() if k != "policy_key"}
        return json.dumps(clean, sort_keys=True)

    def _collect_unused_role_warnings(
        self,
        role_names: set[str],
        policy_views: list[Any],
        warnings: list[str],
    ) -> None:
        referenced: set[str] = set()
        for policy in policy_views:
            role = policy.conditions.get("role")
            if isinstance(role, str):
                referenced.add(role)
        for role in sorted(role_names - referenced):
            warnings.append(f"role '{role}' is defined but never referenced in policies")

    def _collect_duplicate_warnings(self, policy_views: list[Any], warnings: list[str]) -> None:
        seen: dict[tuple[str, str], str] = {}
        for policy in sorted(policy_views, key=lambda item: item.priority):
            conditions = policy.conditions or {}
            key = (policy.action, self._serialize_conditions(conditions))
            previous_effect = seen.get(key)
            effect = policy.effect
            policy_key = conditions.get("policy_key")
            desc = f"{policy_key or policy.action} (priority {policy.priority})"
            if previous_effect:
                if previous_effect == effect:
                    warnings.append(
                        f"policy {desc} is unreachable because a higher-priority policy has identical conditions"
                    )
                else:
                    warnings.append(
                        f"policy {desc} conflicts: higher-priority policy with same conditions returns '{previous_effect}'"
                    )
            else:
                seen[key] = effect
