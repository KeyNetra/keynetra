"""Deprecated compatibility import.

Database-backed audit writing now lives in
``keynetra.infrastructure.repositories.audit``.
"""

from keynetra.infrastructure.repositories.audit import SqlAuditRepository as AuditWriter

__all__ = ["AuditWriter"]
