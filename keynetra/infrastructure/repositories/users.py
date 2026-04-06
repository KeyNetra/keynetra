"""User persistence implementation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from keynetra.domain.models.rbac import Role, User


class SqlUserRepository:
    """SQLAlchemy-backed user context loader."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_context(self, user_id: int) -> dict[str, Any] | None:
        user = (
            self._session.execute(
                select(User)
                .where(User.id == user_id)
                .options(joinedload(User.roles).joinedload(Role.permissions))
            )
            .scalars()
            .first()
        )
        if user is None:
            return None
        permissions: set[str] = set()
        roles: set[str] = set()
        for role in user.roles:
            roles.add(role.name)
            for permission in role.permissions:
                permissions.add(permission.action)
        primary_role = next(iter(sorted(roles)), None)
        return {
            "id": user.id,
            "role": primary_role,
            "roles": sorted(roles),
            "permissions": sorted(permissions),
        }

    def list_user_ids(self, *, tenant_id: int) -> list[int]:
        rows = self._session.execute(select(User.id).order_by(User.id.asc())).scalars().all()
        return [int(row) for row in rows]
