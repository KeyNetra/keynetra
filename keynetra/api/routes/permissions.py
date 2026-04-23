from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor, encode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.models.rbac import Permission, Role, role_permissions
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import (
    PermissionCreate,
    PermissionOut,
    PermissionUpdate,
    RoleOut,
)
from keynetra.services.revisions import RevisionService

router = APIRouter(prefix="/permissions", dependencies=[Depends(get_principal)])


@router.get("", response_model=SuccessResponse[list[PermissionOut]])
def list_permissions(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, object]:
    db = services.db
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


@router.post("", response_model=SuccessResponse[PermissionOut], status_code=HTTPStatus.CREATED)
def create_permission(
    payload: PermissionCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    db = services.db
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
        services.access_index_cache.invalidate_global()
        RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return success_response(
        data=PermissionOut(id=perm.id, action=perm.action).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.put("/{permission_id}", response_model=SuccessResponse[PermissionOut])
def update_permission(
    permission_id: int,
    payload: PermissionUpdate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    db = services.db
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
        services.access_index_cache.invalidate_global()
        RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return success_response(
        data=PermissionOut(id=permission.id, action=permission.action).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.delete("/{permission_id}", response_model=SuccessResponse[dict[str, int]])
def delete_permission(
    permission_id: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    db = services.db
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
        services.access_index_cache.invalidate_global()
        RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
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
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    db = services.db
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
