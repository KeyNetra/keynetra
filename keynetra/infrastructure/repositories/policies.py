"""Policy persistence implementation."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import and_, delete, or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from keynetra.domain.models.policy_versioning import Policy, PolicyVersion
from keynetra.domain.pagination import encode_cursor
from keynetra.engine.keynetra_engine import PolicyDefinition
from keynetra.services.interfaces import PolicyListItem, PolicyMutationResult, PolicyRecord


class SqlPolicyRepository:
    """SQLAlchemy-backed policy repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_current_policies(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[PolicyRecord]:
        try:
            rows = self._current_policy_rows(tenant_id=tenant_id, policy_set=policy_set)
        except OperationalError:
            rows = self._legacy_current_policy_rows(tenant_id=tenant_id)
        records: list[PolicyRecord] = []
        for row in rows:
            if isinstance(row, dict):
                records.append(
                    PolicyRecord(
                        id=int(row["id"]),
                        definition=PolicyDefinition(
                            action=str(row["action"]),
                            effect="allow" if str(row["effect"]) == "allow" else "deny",
                            priority=int(row["priority"]),
                            conditions=dict(row["conditions"] or {}),
                            policy_id=f'{row["policy_key"]}:v{row["version"]}',
                        ),
                    )
                )
                continue
            version, policy = row
            records.append(
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
            )
        return records

    def list_current_policy_views(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[PolicyListItem]:
        try:
            rows = self._current_policy_rows(tenant_id=tenant_id, policy_set=policy_set)
        except OperationalError:
            rows = self._legacy_current_policy_rows(tenant_id=tenant_id)
        items: list[PolicyListItem] = []
        for row in rows:
            if isinstance(row, dict):
                items.append(
                    PolicyListItem(
                        id=int(row["id"]),
                        action=str(row["action"]),
                        effect=str(row["effect"]),
                        priority=int(row["priority"]),
                        state=str(row["state"]),
                        conditions=dict(row["conditions"] or {})
                        | {"policy_key": row["policy_key"], "version": row["version"]},
                    )
                )
                continue
            version, policy = row
            items.append(
                PolicyListItem(
                    id=version.id,
                    action=version.action,
                    effect=version.effect,
                    priority=version.priority,
                    state=version.state,
                    conditions=(version.conditions or {})
                    | {"policy_key": policy.policy_key, "version": version.version},
                )
            )
        return items

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
                state=version.state,
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
        state: str = "active",
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
            state=state,
        )
        self._session.add(policy_version)
        try:
            self._session.commit()
        except OperationalError:
            # Backward compatibility with pre-state schema versions.
            self._session.rollback()
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
            state=policy_version.state,
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

    def list_policy_versions(self, *, tenant_id: int, policy_key: str) -> list[dict[str, Any]]:
        rows = (
            self._session.execute(
                select(PolicyVersion)
                .join(Policy, Policy.id == PolicyVersion.policy_id)
                .where(PolicyVersion.tenant_id == tenant_id)
                .where(Policy.tenant_id == tenant_id)
                .where(Policy.policy_key == policy_key)
                .order_by(PolicyVersion.version.asc())
            )
            .scalars()
            .all()
        )
        return [self._version_to_dict(row) for row in rows]

    def get_policy_version(
        self, *, tenant_id: int, policy_key: str, version: int
    ) -> dict[str, Any] | None:
        row = (
            self._session.execute(
                select(PolicyVersion)
                .join(Policy, Policy.id == PolicyVersion.policy_id)
                .where(PolicyVersion.tenant_id == tenant_id)
                .where(Policy.tenant_id == tenant_id)
                .where(Policy.policy_key == policy_key)
                .where(PolicyVersion.version == version)
            )
            .scalars()
            .first()
        )
        return None if row is None else self._version_to_dict(row)

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

    def _current_policy_rows(
        self, *, tenant_id: int, policy_set: str = "active"
    ) -> list[tuple[PolicyVersion, Policy]]:
        normalized_set = str(policy_set or "active").strip().lower()
        query = (
            select(PolicyVersion, Policy)
            .join(Policy, Policy.id == PolicyVersion.policy_id)
            .where(Policy.tenant_id == tenant_id)
            .where(PolicyVersion.tenant_id == tenant_id)
            .where(PolicyVersion.version == Policy.current_version)
        )
        if normalized_set in {"draft", "archived", "active"}:
            query = query.where(PolicyVersion.state == normalized_set)
        else:
            query = query.where(PolicyVersion.state == "active")
        return self._session.execute(
            query.order_by(PolicyVersion.priority.asc(), PolicyVersion.id.asc())
        ).all()

    def _legacy_current_policy_rows(self, *, tenant_id: int) -> list[dict[str, Any]]:
        rows = self._session.execute(
            text("""
                SELECT pv.id AS id, pv.action AS action, pv.effect AS effect, pv.priority AS priority,
                       pv.conditions AS conditions, pv.version AS version, p.policy_key AS policy_key
                FROM policy_versions pv
                JOIN policies p ON p.id = pv.policy_id
                WHERE p.tenant_id = :tenant_id
                  AND pv.tenant_id = :tenant_id
                  AND pv.version = p.current_version
                ORDER BY pv.priority ASC, pv.id ASC
                """),
            {"tenant_id": tenant_id},
        ).mappings()
        normalized: list[dict[str, Any]] = []
        for row in rows:
            conditions = row.get("conditions")
            if isinstance(conditions, str):
                try:
                    conditions = json.loads(conditions)
                except json.JSONDecodeError:
                    conditions = {}
            normalized.append(
                {
                    "id": int(row["id"]),
                    "action": str(row["action"]),
                    "effect": str(row["effect"]),
                    "priority": int(row["priority"]),
                    "conditions": conditions if isinstance(conditions, dict) else {},
                    "version": int(row["version"]),
                    "policy_key": str(row["policy_key"]),
                    "state": "active",
                }
            )
        return normalized

    @staticmethod
    def _version_to_dict(row: PolicyVersion) -> dict[str, Any]:
        return {
            "id": row.id,
            "version": row.version,
            "action": row.action,
            "effect": row.effect,
            "priority": row.priority,
            "state": row.state,
            "conditions": dict(row.conditions or {}),
            "created_at": row.created_at,
            "created_by": row.created_by,
        }
