"""Seed deterministic demo data for local development."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from keynetra.config.sample_data import (
    SAMPLE_PERMISSIONS,
    SAMPLE_POLICY_DEFINITIONS,
    SAMPLE_RELATIONSHIPS,
    SAMPLE_ROLE,
    SAMPLE_TENANT_KEY,
    SAMPLE_USER,
)
from keynetra.domain.models.policy_versioning import Policy, PolicyVersion
from keynetra.domain.models.rbac import Permission, Role, User, role_permissions, user_roles
from keynetra.domain.models.relationship import Relationship
from keynetra.domain.models.tenant import Tenant

_sample_user = cast(dict[str, Any], SAMPLE_USER)
_sample_role = cast(dict[str, Any], SAMPLE_ROLE)
_sample_relationship = cast(dict[str, Any], SAMPLE_RELATIONSHIPS[0])
_sample_policies = cast(list[dict[str, Any]], SAMPLE_POLICY_DEFINITIONS)


@dataclass(frozen=True)
class SeedSummary:
    tenant_key: str
    created_tenant: bool
    created_user: bool
    created_role: bool
    created_permissions: int
    created_relationships: int
    created_policies: int


def seed_demo_data(
    db: Session, *, tenant_key: str = SAMPLE_TENANT_KEY, reset: bool = False
) -> SeedSummary:
    """Insert deterministic sample tenant data for local development and smoke tests.

    The function is idempotent so it can be run repeatedly in local and CI
    environments without duplicating rows. Pass ``reset=True`` to clear the
    sample dataset for the target tenant before recreating it.
    """

    created_permissions = 0
    created_relationships = 0
    created_policies = 0

    if reset:
        _clear_sample_data(db, tenant_key=tenant_key)

    tenant = db.execute(select(Tenant).where(Tenant.tenant_key == tenant_key)).scalars().first()
    created_tenant = tenant is None
    if tenant is None:
        tenant = Tenant(tenant_key=tenant_key, policy_version=1)
        db.add(tenant)
        db.flush()

    role = db.execute(select(Role).where(Role.name == str(_sample_role["name"]))).scalars().first()
    created_role = role is None
    if role is None:
        role = Role(name=str(_sample_role["name"]))
        db.add(role)
        db.flush()

    for permission_data in SAMPLE_PERMISSIONS:
        action = str(permission_data["action"])
        permission = (
            db.execute(select(Permission).where(Permission.action == action)).scalars().first()
        )
        if permission is None:
            permission = Permission(action=action)
            db.add(permission)
            db.flush()
            created_permissions += 1
        if permission not in role.permissions:
            role.permissions.append(permission)

    user = db.execute(select(User).where(User.id == int(_sample_user["id"]))).scalars().first()
    created_user = user is None
    if user is None:
        user = User(id=int(_sample_user["id"]), external_id=str(_sample_user["external_id"]))
        db.add(user)
        db.flush()
    if role not in user.roles:
        user.roles.append(role)

    relationship = (
        db.execute(
            select(Relationship)
            .where(Relationship.tenant_id == tenant.id)
            .where(Relationship.subject_type == str(_sample_relationship["subject_type"]))
            .where(Relationship.subject_id == str(_sample_relationship["subject_id"]))
            .where(Relationship.relation == str(_sample_relationship["relation"]))
            .where(Relationship.object_type == str(_sample_relationship["object_type"]))
            .where(Relationship.object_id == str(_sample_relationship["object_id"]))
        )
        .scalars()
        .first()
    )
    if relationship is None:
        db.add(
            Relationship(
                tenant_id=tenant.id,
                subject_type=str(_sample_relationship["subject_type"]),
                subject_id=str(_sample_relationship["subject_id"]),
                relation=str(_sample_relationship["relation"]),
                object_type=str(_sample_relationship["object_type"]),
                object_id=str(_sample_relationship["object_id"]),
            )
        )
        created_relationships += 1

    for policy in _sample_policies:
        created_policies += _ensure_policy(
            db,
            tenant_id=tenant.id,
            policy_key=str(policy["policy_key"]),
            action=str(policy["action"]),
            effect=str(policy["effect"]),
            priority=int(policy["priority"]),
            conditions=dict(policy["conditions"]),
        )

    db.commit()
    return SeedSummary(
        tenant_key=tenant.tenant_key,
        created_tenant=created_tenant,
        created_user=created_user,
        created_role=created_role,
        created_permissions=created_permissions,
        created_relationships=created_relationships,
        created_policies=created_policies,
    )


def _clear_sample_data(db: Session, *, tenant_key: str) -> None:
    tenant = db.execute(select(Tenant).where(Tenant.tenant_key == tenant_key)).scalars().first()
    if tenant is None:
        return

    role = db.execute(select(Role).where(Role.name == str(_sample_role["name"]))).scalars().first()
    user = db.execute(select(User).where(User.id == int(_sample_user["id"]))).scalars().first()
    permissions = (
        db.execute(
            select(Permission).where(
                Permission.action.in_([item["action"] for item in SAMPLE_PERMISSIONS])
            )
        )
        .scalars()
        .all()
    )

    if user is not None:
        db.execute(delete(user_roles).where(user_roles.c.user_id == user.id))

    if role is not None:
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == role.id))

    if permissions:
        db.execute(
            delete(role_permissions).where(
                role_permissions.c.permission_id.in_([permission.id for permission in permissions])
            )
        )

    db.execute(delete(PolicyVersion).where(PolicyVersion.tenant_id == tenant.id))
    db.execute(delete(Policy).where(Policy.tenant_id == tenant.id))
    db.execute(delete(Relationship).where(Relationship.tenant_id == tenant.id))
    if role is not None:
        db.execute(delete(Role).where(Role.id == role.id))
    if permissions:
        db.execute(
            delete(Permission).where(
                Permission.id.in_([permission.id for permission in permissions])
            )
        )
    if user is not None:
        db.execute(delete(User).where(User.id == user.id))
    db.execute(delete(Tenant).where(Tenant.id == tenant.id))


def _ensure_policy(
    db: Session,
    *,
    tenant_id: int,
    policy_key: str,
    action: str,
    effect: str,
    priority: int,
    conditions: dict[str, object],
) -> int:
    policy = (
        db.execute(
            select(Policy)
            .where(Policy.tenant_id == tenant_id)
            .where(Policy.policy_key == policy_key)
        )
        .scalars()
        .first()
    )
    if policy is not None:
        return 0

    policy = Policy(tenant_id=tenant_id, policy_key=policy_key, current_version=1)
    db.add(policy)
    db.flush()
    db.add(
        PolicyVersion(
            tenant_id=tenant_id,
            policy_id=policy.id,
            version=1,
            action=action,
            effect=effect,
            priority=priority,
            conditions=conditions,
            created_by="seed-data",
        )
    )
    return 1
