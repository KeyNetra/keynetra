from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor, encode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.redis_client import get_redis
from keynetra.config.security import get_principal
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.domain.models.rbac import Permission, Role, role_permissions
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import (
    PermissionCreate,
    PermissionOut,
    PermissionUpdate,
    RoleOut,
)
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.revisions import RevisionService

router = APIRouter(prefix="/permissions", dependencies=[Depends(get_principal)])


@router.get("", response_model=SuccessResponse[list[PermissionOut]])
def list_permissions(
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("viewer")),
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, object]:
    if limit < 1 or limit > 100:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="limit must be between 1 and 100",
        )
    decoded = decode_cursor(cursor)
    query = select(Permission)
    if decoded is not None:
        query = query.where(
            or_(
                Permission.action > str(decoded["action"]),
                and_(
                    Permission.action == str(decoded["action"]), Permission.id > int(decoded["id"])
                ),
            )
        )
    perms = (
        db.execute(query.order_by(Permission.action.asc(), Permission.id.asc()).limit(limit + 1))
        .scalars()
        .all()
    )
    has_next = len(perms) > limit
    page = perms[:limit]
    next_cursor = (
        encode_cursor({"action": page[-1].action, "id": page[-1].id}) if has_next and page else None
    )
    return success_response(
        data=[PermissionOut(id=p.id, action=p.action).model_dump() for p in page],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.post("", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
def create_permission(
    payload: PermissionCreate,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> PermissionOut:
    existing = (
        db.execute(select(Permission).where(Permission.action == payload.action)).scalars().first()
    )
    if existing:
        raise ApiError(
            status_code=409, code=ApiErrorCode.CONFLICT, message="permission already exists"
        )
    perm = Permission(action=payload.action)
    try:
        db.add(perm)
        db.commit()
        db.refresh(perm)
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return PermissionOut(id=perm.id, action=perm.action)


@router.put("/{permission_id}", response_model=PermissionOut)
def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("developer")),
) -> PermissionOut:
    permission = db.get(Permission, permission_id)
    if permission is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="permission not found")
    existing = (
        db.execute(
            select(Permission)
            .where(Permission.action == payload.action)
            .where(Permission.id != permission_id)
        )
        .scalars()
        .first()
    )
    if existing:
        raise ApiError(
            status_code=409, code=ApiErrorCode.CONFLICT, message="permission already exists"
        )
    permission.action = payload.action
    try:
        db.commit()
        db.refresh(permission)
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return PermissionOut(id=permission.id, action=permission.action)


@router.delete("/{permission_id}", response_model=SuccessResponse[dict[str, int]])
def delete_permission(
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    permission = (
        db.execute(select(Permission).where(Permission.id == permission_id).options())
        .scalars()
        .first()
    )
    if permission is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="permission not found")
    try:
        db.execute(
            delete(role_permissions).where(role_permissions.c.permission_id == permission.id)
        )
        db.delete(permission)
        db.commit()
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return success_response(
        data={"permission_id": permission_id}, request_id=request_id_from_state(request.state)
    )


@router.get("/{permission_id}/roles", response_model=SuccessResponse[list[RoleOut]])
def list_permission_roles(
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    permission = db.get(Permission, permission_id)
    if permission is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="permission not found")
    roles = (
        db.execute(select(Role).where(Role.permissions.any(Permission.id == permission_id)))
        .scalars()
        .all()
    )
    return success_response(
        data=[RoleOut(id=role.id, name=role.name).model_dump() for role in roles],
        request_id=request_id_from_state(request.state),
    )
