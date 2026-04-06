"""ACL persistence implementation."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keynetra.domain.models.acl import ResourceACL
from keynetra.services.interfaces import ACLRecord


class SqlACLRepository:
    """SQLAlchemy-backed ACL repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

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
    ) -> int:
        row = ResourceACL(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            effect=effect,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row.id

    def list_resource_acl(
        self, *, tenant_id: int, resource_type: str, resource_id: str
    ) -> list[ACLRecord]:
        rows = (
            self._session.execute(
                select(ResourceACL)
                .where(ResourceACL.tenant_id == tenant_id)
                .where(ResourceACL.resource_type == resource_type)
                .where(ResourceACL.resource_id == resource_id)
                .order_by(ResourceACL.action.asc(), ResourceACL.id.asc())
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_acl_entry(self, *, tenant_id: int, acl_id: int) -> ACLRecord | None:
        row = (
            self._session.execute(
                select(ResourceACL)
                .where(ResourceACL.tenant_id == tenant_id)
                .where(ResourceACL.id == acl_id)
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_record(row)

    def find_matching_acl(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> list[ACLRecord]:
        rows = (
            self._session.execute(
                select(ResourceACL)
                .where(ResourceACL.tenant_id == tenant_id)
                .where(ResourceACL.resource_type == resource_type)
                .where(ResourceACL.resource_id == resource_id)
                .where(ResourceACL.action == action)
                .order_by(ResourceACL.id.asc())
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def delete_acl_entry(self, *, tenant_id: int, acl_id: int) -> None:
        self._session.execute(
            delete(ResourceACL)
            .where(ResourceACL.tenant_id == tenant_id)
            .where(ResourceACL.id == acl_id)
        )
        self._session.commit()

    def _to_record(self, row: ResourceACL) -> ACLRecord:
        return ACLRecord(
            id=row.id,
            tenant_id=row.tenant_id,
            subject_type=row.subject_type,
            subject_id=row.subject_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            action=row.action,
            effect=row.effect,
            created_at=row.created_at,
        )
