"""Deprecated compatibility import.

Database-backed policy storage now lives in
``keynetra.infrastructure.repositories.policies``.
"""

from keynetra.infrastructure.repositories.policies import SqlPolicyRepository as PolicyStore

__all__ = ["PolicyStore"]
