"""Persistence for API idempotency records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from keynetra.domain.models.idempotency import IdempotencyRecord


@dataclass(frozen=True)
class IdempotencyStartResult:
    """Result of claiming or replaying an idempotent request."""

    outcome: str
    record_id: int | None = None
    status_code: int | None = None
    response_body: str | None = None
    content_type: str | None = None


class SqlIdempotencyRepository:
    """SQLAlchemy-backed storage for idempotent write requests."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self, *, scope: str, idempotency_key: str, request_hash: str
    ) -> IdempotencyStartResult:
        record = IdempotencyRecord(
            scope=scope, idempotency_key=idempotency_key, request_hash=request_hash
        )
        self._session.add(record)
        try:
            self._session.commit()
            self._session.refresh(record)
            return IdempotencyStartResult(outcome="started", record_id=record.id)
        except IntegrityError:
            self._session.rollback()
            existing = self._get(scope=scope, idempotency_key=idempotency_key)
            if existing is None:
                raise
            if existing.request_hash != request_hash:
                return IdempotencyStartResult(outcome="mismatch")
            if existing.response_status_code is None or existing.response_body is None:
                return IdempotencyStartResult(outcome="pending")
            return IdempotencyStartResult(
                outcome="replay",
                record_id=existing.id,
                status_code=existing.response_status_code,
                response_body=existing.response_body,
                content_type=existing.response_content_type,
            )

    def complete(
        self,
        *,
        record_id: int,
        status_code: int,
        response_body: str,
        content_type: str | None,
    ) -> None:
        record = self._session.get(IdempotencyRecord, record_id)
        if record is None:
            return
        record.response_status_code = status_code
        record.response_body = response_body
        record.response_content_type = content_type
        record.completed_at = datetime.now(UTC)
        self._session.commit()

    def _get(self, *, scope: str, idempotency_key: str) -> IdempotencyRecord | None:
        return (
            self._session.execute(
                select(IdempotencyRecord)
                .where(IdempotencyRecord.scope == scope)
                .where(IdempotencyRecord.idempotency_key == idempotency_key)
            )
            .scalars()
            .first()
        )
