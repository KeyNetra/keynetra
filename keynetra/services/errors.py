"""Service-layer exceptions."""

from __future__ import annotations


class TenantNotFoundError(LookupError):
    """Raised when a tenant-scoped request targets an unknown tenant."""

    def __init__(self, tenant_key: str) -> None:
        self.tenant_key = tenant_key
        super().__init__(f"tenant '{tenant_key}' not found")
