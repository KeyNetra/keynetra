"""Relationship persistence implementation."""

from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from keynetra.api.pagination import encode_cursor
from keynetra.domain.models.relationship import Relationship
from keynetra.services.interfaces import RelationshipRecord


class SqlRelationshipRepository:
    """SQLAlchemy-backed relationship repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_subject(
        self, *, tenant_id: int, subject_type: str, subject_id: str
    ) -> list[RelationshipRecord]:
        rows = (
            self._session.execute(
                select(Relationship)
                .where(Relationship.tenant_id == tenant_id)
                .where(Relationship.subject_type == subject_type)
                .where(Relationship.subject_id == subject_id)
                .order_by(
                    Relationship.relation.asc(),
                    Relationship.object_type.asc(),
                    Relationship.object_id.asc(),
                    Relationship.id.asc(),
                )
            )
            .scalars()
            .all()
        )
        return [
            RelationshipRecord(
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                relation=row.relation,
                object_type=row.object_type,
                object_id=row.object_id,
            )
            for row in rows
        ]

    def list_for_subject_page(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        limit: int,
        cursor: dict[str, object] | None,
    ) -> tuple[list[RelationshipRecord], str | None]:
        query = (
            select(Relationship)
            .where(Relationship.tenant_id == tenant_id)
            .where(Relationship.subject_type == subject_type)
            .where(Relationship.subject_id == subject_id)
        )
        if cursor is not None:
            query = query.where(
                or_(
                    Relationship.relation > str(cursor["relation"]),
                    and_(
                        Relationship.relation == str(cursor["relation"]),
                        Relationship.object_type > str(cursor["object_type"]),
                    ),
                    and_(
                        Relationship.relation == str(cursor["relation"]),
                        Relationship.object_type == str(cursor["object_type"]),
                        Relationship.object_id > str(cursor["object_id"]),
                    ),
                    and_(
                        Relationship.relation == str(cursor["relation"]),
                        Relationship.object_type == str(cursor["object_type"]),
                        Relationship.object_id == str(cursor["object_id"]),
                        Relationship.id > int(cursor["id"]),
                    ),
                )
            )
        rows = (
            self._session.execute(
                query.order_by(
                    Relationship.relation.asc(),
                    Relationship.object_type.asc(),
                    Relationship.object_id.asc(),
                    Relationship.id.asc(),
                ).limit(limit + 1)
            )
            .scalars()
            .all()
        )
        has_next = len(rows) > limit
        page_rows = rows[:limit]
        items = [
            RelationshipRecord(
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                relation=row.relation,
                object_type=row.object_type,
                object_id=row.object_id,
            )
            for row in page_rows
        ]
        next_cursor = None
        if has_next and page_rows:
            last = page_rows[-1]
            next_cursor = encode_cursor(
                {
                    "relation": last.relation,
                    "object_type": last.object_type,
                    "object_id": last.object_id,
                    "id": last.id,
                }
            )
        return items, next_cursor

    def list_for_object(
        self, *, tenant_id: int, object_type: str, object_id: str
    ) -> list[RelationshipRecord]:
        rows = (
            self._session.execute(
                select(Relationship)
                .where(Relationship.tenant_id == tenant_id)
                .where(Relationship.object_type == object_type)
                .where(Relationship.object_id == object_id)
                .order_by(
                    Relationship.subject_type.asc(),
                    Relationship.subject_id.asc(),
                    Relationship.relation.asc(),
                    Relationship.id.asc(),
                )
            )
            .scalars()
            .all()
        )
        return [
            RelationshipRecord(
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                relation=row.relation,
                object_type=row.object_type,
                object_id=row.object_id,
            )
            for row in rows
        ]

    def create(
        self,
        *,
        tenant_id: int,
        subject_type: str,
        subject_id: str,
        relation: str,
        object_type: str,
        object_id: str,
    ) -> int:
        row = Relationship(
            tenant_id=tenant_id,
            subject_type=subject_type,
            subject_id=subject_id,
            relation=relation,
            object_type=object_type,
            object_id=object_id,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row.id
