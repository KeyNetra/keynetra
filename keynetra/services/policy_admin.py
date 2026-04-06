"""Deprecated compatibility wrapper.

Policy orchestration now lives in ``keynetra.services.policies``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from keynetra.config.settings import get_settings
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.cache.policy_distribution import RedisPolicyEventPublisher
from keynetra.infrastructure.repositories.policies import SqlPolicyRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.services.policies import PolicyService


class PolicyAdmin:
    """Backward-compatible adapter around the new policy service."""

    def create_policy_version(
        self,
        db: Session,
        *,
        tenant_id: int,
        policy_key: str,
        action: str,
        effect: str,
        priority: int,
        conditions: dict[str, Any],
        created_by: str | None,
    ) -> Any:
        settings = get_settings()
        tenants = SqlTenantRepository(db)
        tenant = tenants.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("tenant not found")
        service = PolicyService(
            tenants=tenants,
            policies=SqlPolicyRepository(db),
            policy_cache=build_policy_cache(None),
            decision_cache=build_decision_cache(None),
            publisher=RedisPolicyEventPublisher(settings),
        )
        return service.create_policy(
            tenant_key=tenant.tenant_key,
            policy_key=policy_key,
            action=action,
            effect=effect,
            priority=priority,
            conditions=conditions,
            created_by=created_by,
        )

    def rollback_policy(self, db: Session, *, tenant_id: int, policy_key: str, version: int) -> Any:
        settings = get_settings()
        tenants = SqlTenantRepository(db)
        tenant = tenants.get_by_id(tenant_id)
        if tenant is None:
            raise ValueError("tenant not found")
        service = PolicyService(
            tenants=tenants,
            policies=SqlPolicyRepository(db),
            policy_cache=build_policy_cache(None),
            decision_cache=build_decision_cache(None),
            publisher=RedisPolicyEventPublisher(settings),
        )
        policy_name, current_version = service.rollback_policy(
            tenant_key=tenant.tenant_key,
            policy_key=policy_key,
            version=version,
        )
        return type(
            "RollbackPolicyResult",
            (),
            {"policy_key": policy_name, "current_version": current_version},
        )()
