"""Distributed access indexing for ACL and relationship lookups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from keynetra.services.interfaces import (
    AccessIndexCache,
    AccessIndexEntry,
    ACLCache,
    ACLRepository,
    RelationshipRecord,
    RelationshipRepository,
)


@dataclass(frozen=True)
class AccessSubject:
    subject_type: str
    subject_id: str

    def to_descriptor(self) -> str:
        return f"{self.subject_type}:{self.subject_id}"


def relationship_descriptor(relationship: RelationshipRecord) -> str:
    return (
        f"relationship:{relationship.relation}:{relationship.object_type}:{relationship.object_id}"
    )


class AccessIndexer:
    """Builds resource/action access indices from ACL and relationship data."""

    def __init__(
        self,
        *,
        acl_repository: ACLRepository,
        acl_cache: ACLCache,
        access_index_cache: AccessIndexCache,
        relationships: RelationshipRepository,
    ) -> None:
        self._acl_repository = acl_repository
        self._acl_cache = acl_cache
        self._access_index_cache = access_index_cache
        self._relationships = relationships

    def build_resource_index(
        self,
        *,
        tenant_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> list[AccessIndexEntry]:
        cached = self._access_index_cache.get(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
        if cached is not None:
            return cached

        acl_entries = self._acl_cache.get(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
        if acl_entries is None:
            acl_entries = self._acl_repository.find_matching_acl(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            )
            self._acl_cache.set(
                tenant_id=tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                acl_entries=acl_entries,
            )

        relationship_rows = self._relationships.list_for_object(
            tenant_id=tenant_id,
            object_type=resource_type,
            object_id=resource_id,
        )

        entries = [
            AccessIndexEntry(
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                allowed_subjects=(self._subject_descriptor(acl.subject_type, acl.subject_id),),
                source="acl",
                subject_type=acl.subject_type,
                subject_id=acl.subject_id,
                effect=acl.effect,
                acl_id=acl.id,
            )
            for acl in acl_entries
        ]
        if relationship_rows:
            entries.append(
                AccessIndexEntry(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    allowed_subjects=tuple(
                        sorted(
                            {
                                (
                                    self._subject_descriptor(row.subject_type, row.subject_id)
                                    if row.subject_type != "relationship"
                                    else relationship_descriptor(row)
                                )
                                for row in relationship_rows
                            }
                        )
                    ),
                    source="relationship",
                )
            )

        self._access_index_cache.set(
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            entries=entries,
        )
        return entries

    def invalidate_resource(self, *, tenant_id: int, resource_type: str, resource_id: str) -> None:
        self._acl_cache.invalidate(
            tenant_id=tenant_id, resource_type=resource_type, resource_id=resource_id
        )
        self._access_index_cache.invalidate(
            tenant_id=tenant_id, resource_type=resource_type, resource_id=resource_id
        )

    def invalidate_tenant(self, *, tenant_id: int) -> None:
        self._access_index_cache.invalidate_tenant(tenant_id=tenant_id)

    def subject_descriptors(self, user: dict[str, Any]) -> set[str]:
        descriptors: set[str] = set()
        user_id = user.get("id")
        if user_id is not None:
            descriptors.add(self._subject_descriptor("user", str(user_id)))
        roles = user.get("roles", [])
        if isinstance(roles, list):
            descriptors.update(
                self._subject_descriptor("role", str(role)) for role in roles if role is not None
            )
        permissions = user.get("permissions", [])
        if isinstance(permissions, list):
            descriptors.update(
                self._subject_descriptor("permission", str(permission))
                for permission in permissions
                if permission is not None
            )
        relations = user.get("relations", [])
        if isinstance(relations, list):
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                relation_type = str(relation.get("relation", ""))
                object_type = str(relation.get("object_type", ""))
                object_id = str(relation.get("object_id", ""))
                if relation_type and object_type and object_id:
                    descriptors.add(f"relationship:{relation_type}:{object_type}:{object_id}")
        return descriptors

    def _subject_descriptor(self, subject_type: str, subject_id: str) -> str:
        return f"{subject_type}:{subject_id}"
