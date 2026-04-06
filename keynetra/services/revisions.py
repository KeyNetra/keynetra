"""Authorization consistency revisions."""

from __future__ import annotations

from keynetra.observability.metrics import record_revision_update
from keynetra.services.interfaces import TenantRepository


class RevisionService:
    """Monotonic revision counter helper."""

    def __init__(self, tenants: TenantRepository) -> None:
        self._tenants = tenants

    def get_revision(self, *, tenant_key: str) -> int:
        tenant = self._tenants.get_or_create(tenant_key)
        return int(getattr(tenant, "revision", 1))

    def bump_revision(self, *, tenant_key: str) -> int:
        tenant = self._tenants.get_or_create(tenant_key)
        bump = getattr(self._tenants, "bump_revision", None)
        if callable(bump):
            updated = bump(tenant)
            revision = int(getattr(updated, "revision", 1))
            if revision != int(getattr(tenant, "revision", 1)):
                record_revision_update(tenant=tenant_key)
            return revision
        return int(getattr(tenant, "revision", 1))
