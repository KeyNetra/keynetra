"""Deprecated compatibility import.

Database-backed tenant storage now lives in
``keynetra.infrastructure.repositories.tenants``.
"""

from keynetra.infrastructure.repositories.tenants import SqlTenantRepository as TenantStore

__all__ = ["TenantStore"]
