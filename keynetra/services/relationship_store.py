"""Deprecated compatibility import.

Database-backed relationship storage now lives in
``keynetra.infrastructure.repositories.relationships``.
"""

from keynetra.infrastructure.repositories.relationships import (
    SqlRelationshipRepository as RelationshipStore,
)

__all__ = ["RelationshipStore"]
