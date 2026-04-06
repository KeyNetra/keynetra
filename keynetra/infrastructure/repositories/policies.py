"""Policy persistence implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from keynetra.api.pagination import encode_cursor
from keynetra.domain.models.policy_versioning import Policy, PolicyVersion
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.services.interfaces import PolicyListItem, PolicyMutationResult, PolicyRecord


class SqlPolicyRepository:
    """SQLAlchemy-backed policy repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_current_policies(self, *, tenant_id: int) -> list[PolicyRecord]:
        rows = self._current_policy_rows(tenant_id=tenant_id)
        return [
            PolicyRecord(
                id=version.id,
                definition=PolicyDefinition(
                    action=version.action,
                    effect="allow" if version.effect == "allow" else "deny",
                    priority=version.priority,
                    conditions=dict(version.conditions or {}),
                    policy_id=f"{policy.policy_key}:v{version.version}",
                ),
            )
            for version, policy in rows
        ]

    def list_current_policy_views(self, *, tenant_id: int) -> list[PolicyListItem]:
        rows = self._current_policy_rows(tenant_id=tenant_id)
        return [
            PolicyListItem(
                id=version.id,
                action=version.action,
                effect=version.effect,
                priority=version.priority,
                conditions=(version.conditions or {})
                | {"policy_key": policy.policy_key, "version": version.version},
            )
            for version, policy in rows
        ]

    def list_current_policy_page(
        self,
        *,
        tenant_id: int,
        limit: int,
        cursor: dict[str, Any] | None,
    ) -> tuple[list[PolicyListItem], str | None]:
        query = (
            select(PolicyVersion, Policy)
            .join(Policy, Policy.id == PolicyVersion.policy_id)
            .where(Policy.tenant_id == tenant_id)
            .where(PolicyVersion.tenant_id == tenant_id)
            .where(PolicyVersion.version == Policy.current_version)
        )
        if cursor is not None:
            query = query.where(
                or_(
                    PolicyVersion.priority > int(cursor["priority"]),
                    and_(
                        PolicyVersion.priority == int(cursor["priority"]),
                        PolicyVersion.id > int(cursor["id"]),
                    ),
                )
            )
        rows = self._session.execute(
            query.order_by(PolicyVersion.priority.asc(), PolicyVersion.id.asc()).limit(limit + 1)
        ).all()
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        items = [
            PolicyListItem(
                id=version.id,
                action=version.action,
                effect=version.effect,
                priority=version.priority,
                conditions=(version.conditions or {})
                | {"policy_key": policy.policy_key, "version": version.version},
            )
            for version, policy in page_rows
        ]
        next_cursor = None
        if has_next and page_rows:
            last_version, _ = page_rows[-1]
            next_cursor = encode_cursor({"priority": last_version.priority, "id": last_version.id})
        return items, next_cursor

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
    ) -> PolicyMutationResult:
        policy = (
            self._session.execute(
                select(Policy)
                .where(Policy.tenant_id == tenant_id)
                .where(Policy.policy_key == policy_key)
            )
            .scalars()
            .first()
        )
        if policy is None:
            policy = Policy(tenant_id=tenant_id, policy_key=policy_key, current_version=1)
            self._session.add(policy)
            self._session.flush()
            next_version = 1
        else:
            next_version = int(policy.current_version) + 1
            policy.current_version = next_version

        policy_version = PolicyVersion(
            tenant_id=tenant_id,
            policy_id=policy.id,
            version=next_version,
            action=action,
            effect=effect,
            priority=priority,
            conditions=conditions,
            created_by=created_by,
        )
        self._session.add(policy_version)
        self._session.commit()
        self._session.refresh(policy_version)
        return PolicyMutationResult(
            id=policy_version.id,
            action=policy_version.action,
            effect=policy_version.effect,
            priority=policy_version.priority,
            conditions=dict(policy_version.conditions or {}),
        )

    def rollback_policy(self, *, tenant_id: int, policy_key: str, version: int) -> tuple[str, int]:
        policy = (
            self._session.execute(
                select(Policy)
                .where(Policy.tenant_id == tenant_id)
                .where(Policy.policy_key == policy_key)
            )
            .scalars()
            .first()
        )
        if policy is None:
            raise ValueError("policy not found")
        existing = (
            self._session.execute(
                select(PolicyVersion)
                .where(PolicyVersion.tenant_id == tenant_id)
                .where(PolicyVersion.policy_id == policy.id)
                .where(PolicyVersion.version == version)
            )
            .scalars()
            .first()
        )
        if existing is None:
            raise ValueError("version not found")
        policy.current_version = version
        self._session.commit()
        self._session.refresh(policy)
        return policy.policy_key, int(policy.current_version)

    def delete_policy(self, *, tenant_id: int, policy_key: str) -> None:
        policy = (
            self._session.execute(
                select(Policy)
                .where(Policy.tenant_id == tenant_id)
                .where(Policy.policy_key == policy_key)
            )
            .scalars()
            .first()
        )
        if policy is None:
            return
        self._session.execute(
            delete(PolicyVersion)
            .where(PolicyVersion.tenant_id == tenant_id)
            .where(PolicyVersion.policy_id == policy.id)
        )
        self._session.execute(delete(Policy).where(Policy.id == policy.id))
        self._session.commit()

    def _current_policy_rows(self, *, tenant_id: int) -> list[tuple[PolicyVersion, Policy]]:
        return self._session.execute(
            select(PolicyVersion, Policy)
            .join(Policy, Policy.id == PolicyVersion.policy_id)
            .where(Policy.tenant_id == tenant_id)
            .where(PolicyVersion.tenant_id == tenant_id)
            .where(PolicyVersion.version == Policy.current_version)
            .order_by(PolicyVersion.priority.asc(), PolicyVersion.id.asc())
        ).all()
