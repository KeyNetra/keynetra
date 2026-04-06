"""Audit persistence implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, and_, desc, func, or_, select
from sqlalchemy.orm import Session

from keynetra.api.pagination import encode_cursor
from keynetra.domain.models.audit import AuditLog
from keynetra.engine.keynetra_engine import AuthorizationDecision, AuthorizationInput
from keynetra.services.interfaces import AuditListItem


class SqlAuditRepository:
    """SQLAlchemy-backed audit writer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def write(
        self,
        *,
        tenant_id: int,
        principal_type: str,
        principal_id: str,
        authorization_input: AuthorizationInput,
        decision: AuthorizationDecision,
        correlation_id: str | None = None,
    ) -> None:
        row = AuditLog(
            tenant_id=tenant_id,
            principal_type=principal_type,
            principal_id=principal_id,
            correlation_id=correlation_id,
            user=authorization_input.user,
            action=authorization_input.action,
            resource=authorization_input.resource,
            decision=decision.decision.upper(),
            matched_policies=list(decision.matched_policies),
            reason=decision.reason,
            evaluated_rules=[step.to_dict() for step in decision.explain_trace],
            failed_conditions=list(decision.failed_conditions),
        )
        self._session.add(row)
        self._session.commit()

    def list_page(
        self,
        *,
        tenant_id: int,
        limit: int,
        cursor: dict | None,
        user_id: str | None,
        resource_id: str | None,
        decision: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> tuple[list[AuditListItem], str | None]:
        query = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        if user_id:
            query = query.where(self._json_field(AuditLog.user, "id") == user_id)
        if resource_id:
            query = query.where(
                or_(
                    self._json_field(AuditLog.resource, "id") == resource_id,
                    self._json_field(AuditLog.resource, "resource_id") == resource_id,
                )
            )
        if decision:
            query = query.where(AuditLog.decision == decision.upper())
        if start_time:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            query = query.where(AuditLog.created_at <= end_time)
        if cursor is not None:
            cursor_created_at = datetime.fromisoformat(str(cursor["created_at"]))
            cursor_id = int(cursor["id"])
            query = query.where(
                or_(
                    AuditLog.created_at < cursor_created_at,
                    and_(AuditLog.created_at == cursor_created_at, AuditLog.id < cursor_id),
                )
            )

        rows = (
            self._session.execute(
                query.order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(limit + 1)
            )
            .scalars()
            .all()
        )
        has_next = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            encode_cursor({"created_at": page[-1].created_at.isoformat(), "id": page[-1].id})
            if has_next and page
            else None
        )
        return [self._to_item(row) for row in page], next_cursor

    def _json_field(self, column, key: str):
        dialect = self._session.bind.dialect.name if self._session.bind is not None else ""
        if dialect == "postgresql":
            return column[key].as_string()
        return func.json_extract(column, f"$.{key}", type_=String)

    @staticmethod
    def _to_item(row: AuditLog) -> AuditListItem:
        return AuditListItem(
            id=row.id,
            principal_type=row.principal_type,
            principal_id=row.principal_id,
            correlation_id=row.correlation_id,
            user=row.user,
            action=row.action,
            resource=row.resource,
            decision=row.decision,
            matched_policies=list(row.matched_policies),
            reason=row.reason,
            evaluated_rules=list(row.evaluated_rules),
            failed_conditions=list(row.failed_conditions),
            created_at=row.created_at,
        )
