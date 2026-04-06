"""Relationship orchestration service."""

from __future__ import annotations

from keynetra.services.interfaces import (
    AccessIndexCache,
    DecisionCache,
    RelationshipCache,
    RelationshipRepository,
    TenantRepository,
)
from keynetra.services.revisions import RevisionService


class RelationshipService:
    """Orchestrates relationship reads, writes, and invalidation."""

    def __init__(
        self,
        *,
        tenants: TenantRepository,
        relationships: RelationshipRepository,
        relationship_cache: RelationshipCache,
        decision_cache: DecisionCache,
        access_index_cache: AccessIndexCache | None = None,
    ) -> None:
        self._tenants = tenants
        self._relationships = relationships
        self._relationship_cache = relationship_cache
        self._decision_cache = decision_cache
        self._access_index_cache = access_index_cache
        self._revisions = RevisionService(tenants)

    def list_relationships(
        self, *, tenant_key: str, subject_type: str, subject_id: str
    ) -> list[dict[str, str]]:
        tenant = self._tenants.get_or_create(tenant_key)
        cached = self._relationship_cache.get(
            tenant_id=tenant.id, subject_type=subject_type, subject_id=subject_id
        )
        relationships = cached
        if relationships is None:
            relationships = self._relationships.list_for_subject(
                tenant_id=tenant.id,
                subject_type=subject_type,
                subject_id=subject_id,
            )
            self._relationship_cache.set(
                tenant_id=tenant.id,
                subject_type=subject_type,
                subject_id=subject_id,
                relationships=relationships,
            )
        return [relationship.to_dict() for relationship in relationships]

    def list_relationships_page(
        self,
        *,
        tenant_key: str,
        subject_type: str,
        subject_id: str,
        limit: int,
        cursor: dict[str, object] | None,
    ) -> tuple[list[dict[str, str]], str | None]:
        tenant = self._tenants.get_or_create(tenant_key)
        relationships, next_cursor = self._relationships.list_for_subject_page(
            tenant_id=tenant.id,
            subject_type=subject_type,
            subject_id=subject_id,
            limit=limit,
            cursor=cursor,
        )
        return [relationship.to_dict() for relationship in relationships], next_cursor

    def create_relationship(
        self,
        *,
        tenant_key: str,
        subject_type: str,
        subject_id: str,
        relation: str,
        object_type: str,
        object_id: str,
    ) -> int:
        tenant = self._tenants.get_or_create(tenant_key)
        row_id = self._relationships.create(
            tenant_id=tenant.id,
            subject_type=subject_type,
            subject_id=subject_id,
            relation=relation,
            object_type=object_type,
            object_id=object_id,
        )
        self._relationship_cache.invalidate(
            tenant_id=tenant.id, subject_type=subject_type, subject_id=subject_id
        )
        if self._access_index_cache is not None:
            self._access_index_cache.invalidate_tenant(tenant_id=tenant.id)
        self._decision_cache.bump_namespace(tenant.tenant_key)
        self._revisions.bump_revision(tenant_key=tenant.tenant_key)
        return row_id
