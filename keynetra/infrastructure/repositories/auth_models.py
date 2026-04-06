"""Authorization model persistence implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from keynetra.domain.models.auth_model import AuthorizationModel
from keynetra.services.interfaces import AuthModelRecord


class SqlAuthModelRepository:
    """SQLAlchemy-backed authorization model repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_model(self, *, tenant_id: int) -> AuthModelRecord | None:
        row = (
            self._session.execute(
                select(AuthorizationModel).where(AuthorizationModel.tenant_id == tenant_id)
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_record(row)

    def upsert_model(
        self,
        *,
        tenant_id: int,
        schema_text: str,
        schema_json: dict,
        compiled_json: dict,
    ) -> AuthModelRecord:
        row = (
            self._session.execute(
                select(AuthorizationModel).where(AuthorizationModel.tenant_id == tenant_id)
            )
            .scalars()
            .first()
        )
        if row is None:
            row = AuthorizationModel(
                tenant_id=tenant_id,
                schema_text=schema_text,
                schema_json=schema_json,
                compiled_json=compiled_json,
            )
            self._session.add(row)
        else:
            row.schema_text = schema_text
            row.schema_json = schema_json
            row.compiled_json = compiled_json
        self._session.commit()
        self._session.refresh(row)
        return self._to_record(row)

    def _to_record(self, row: AuthorizationModel) -> AuthModelRecord:
        return AuthModelRecord(
            id=row.id,
            tenant_id=row.tenant_id,
            schema_text=row.schema_text,
            schema_json=dict(row.schema_json or {}),
            compiled_json=dict(row.compiled_json or {}),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
