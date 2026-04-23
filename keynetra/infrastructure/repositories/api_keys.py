"""API key persistence implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from keynetra.domain.models.api_key import ApiKey
from keynetra.services.interfaces import ApiKeyRecord
from keynetra.utils.datetime import utc_now


class SqlApiKeyRepository:
    """SQLAlchemy-backed API key repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_keys(self, *, tenant_id: int) -> list[ApiKeyRecord]:
        rows = (
            self._session.execute(
                select(ApiKey).where(ApiKey.tenant_id == tenant_id).order_by(ApiKey.id.asc())
            )
            .scalars()
            .all()
        )
        return [self._to_record(row) for row in rows]

    def get_key(self, *, tenant_id: int, key_id: int) -> ApiKeyRecord | None:
        row = (
            self._session.execute(
                select(ApiKey).where(ApiKey.tenant_id == tenant_id).where(ApiKey.id == key_id)
            )
            .scalars()
            .first()
        )
        return None if row is None else self._to_record(row)

    def get_by_hash(self, *, key_hash: str) -> ApiKeyRecord | None:
        row = (
            self._session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
            .scalars()
            .first()
        )
        return None if row is None else self._to_record(row)

    def create_key(
        self,
        *,
        tenant_id: int,
        name: str,
        key_hash: str,
        scopes: dict[str, object],
    ) -> ApiKeyRecord:
        row = ApiKey(tenant_id=tenant_id, name=name, key_hash=key_hash, scopes_json=scopes)
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_record(row)

    def revoke_key(self, *, tenant_id: int, key_id: int) -> None:
        row = (
            self._session.execute(
                select(ApiKey).where(ApiKey.tenant_id == tenant_id).where(ApiKey.id == key_id)
            )
            .scalars()
            .first()
        )
        if row is None:
            return
        row.revoked_at = row.revoked_at or utc_now()
        self._session.commit()

    def _to_record(self, row: ApiKey) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            key_hash=row.key_hash,
            scopes=dict(row.scopes_json or {}),
            created_at=row.created_at,
            revoked_at=row.revoked_at,
        )
