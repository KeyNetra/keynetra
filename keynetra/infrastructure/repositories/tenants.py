"""Tenant persistence implementation.

This module owns database access. Services should depend on the
``TenantRepository`` protocol instead of SQLAlchemy details.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from keynetra.domain.models.tenant import Tenant
from keynetra.services.interfaces import TenantRecord


class SqlTenantRepository:
    """SQLAlchemy-backed tenant repository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, tenant_id: int) -> TenantRecord | None:
        tenant = (
            self._session.execute(select(Tenant).where(Tenant.id == tenant_id)).scalars().first()
        )
        if tenant is None:
            return None
        return self._to_record(tenant)

    def get_or_create(self, tenant_key: str) -> TenantRecord:
        existing = (
            self._session.execute(select(Tenant).where(Tenant.tenant_key == tenant_key))
            .scalars()
            .first()
        )
        if existing is not None:
            return self._to_record(existing)
        tenant = Tenant(tenant_key=tenant_key)
        self._session.add(tenant)
        self._session.commit()
        self._session.refresh(tenant)
        return self._to_record(tenant)

    def bump_policy_version(self, tenant: TenantRecord) -> TenantRecord:
        row = self._session.execute(select(Tenant).where(Tenant.id == tenant.id)).scalars().first()
        if row is None:
            raise ValueError("tenant not found")
        row.policy_version = int(row.policy_version) + 1
        self._session.commit()
        self._session.refresh(row)
        return self._to_record(row)

    def bump_revision(self, tenant: TenantRecord) -> TenantRecord:
        row = self._session.execute(select(Tenant).where(Tenant.id == tenant.id)).scalars().first()
        if row is None:
            raise ValueError("tenant not found")
        row.authorization_revision = int(row.authorization_revision) + 1
        self._session.commit()
        self._session.refresh(row)
        return self._to_record(row)

    def _to_record(self, tenant: Tenant) -> TenantRecord:
        return TenantRecord(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=int(tenant.policy_version),
            revision=int(getattr(tenant, "authorization_revision", 1)),
        )
