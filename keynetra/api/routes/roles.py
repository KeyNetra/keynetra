from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor, encode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.redis_client import get_redis
from keynetra.config.security import get_principal
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.domain.models.rbac import Permission, Role, role_permissions, user_roles
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import PermissionOut, RoleCreate, RoleOut, RoleUpdate
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.revisions import RevisionService

router = APIRouter(prefix="/roles", dependencies=[Depends(get_principal)])


@router.get("", response_model=SuccessResponse[list[RoleOut]])
def list_roles(
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
    query = select(Role)
    if decoded is not None:
        query = query.where(
            or_(
                Role.name > str(decoded["name"]),
                and_(Role.name == str(decoded["name"]), Role.id > int(decoded["id"])),
            )
        )
    roles = (
        db.execute(query.order_by(Role.name.asc(), Role.id.asc()).limit(limit + 1)).scalars().all()
    )
    has_next = len(roles) > limit
    page = roles[:limit]
    next_cursor = (
        encode_cursor({"name": page[-1].name, "id": page[-1].id}) if has_next and page else None
    )
    return success_response(
        data=[RoleOut(id=r.id, name=r.name).model_dump() for r in page],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> RoleOut:
    existing = db.execute(select(Role).where(Role.name == payload.name)).scalars().first()
    if existing:
        raise ApiError(status_code=409, code=ApiErrorCode.CONFLICT, message="role already exists")
    role = Role(name=payload.name)
    try:
        db.add(role)
        db.commit()
        db.refresh(role)
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return RoleOut(id=role.id, name=role.name)


@router.put("/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("developer")),
) -> RoleOut:
    role = db.get(Role, role_id)
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    existing = (
        db.execute(select(Role).where(Role.name == payload.name).where(Role.id != role_id))
        .scalars()
        .first()
    )
    if existing:
        raise ApiError(status_code=409, code=ApiErrorCode.CONFLICT, message="role already exists")
    role.name = payload.name
    try:
        db.commit()
        db.refresh(role)
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return RoleOut(id=role.id, name=role.name)


@router.delete("/{role_id}", response_model=SuccessResponse[dict[str, int]])
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    role = (
        db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(joinedload(Role.permissions), joinedload(Role.users))
        )
        .unique()
        .scalars()
        .first()
    )
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    try:
        db.execute(delete(role_permissions).where(role_permissions.c.role_id == role.id))
        db.execute(delete(user_roles).where(user_roles.c.role_id == role.id))
        db.delete(role)
        db.commit()
        build_access_index_cache(get_redis()).invalidate_global()
        RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
    except SQLAlchemyError as e:
        db.rollback()
        raise ApiError(status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error") from e
    return success_response(
        data={"role_id": role_id}, request_id=request_id_from_state(request.state)
    )


@router.get("/{role_id}/permissions", response_model=SuccessResponse[list[PermissionOut]])
def list_role_permissions(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    role = (
        db.execute(select(Role).where(Role.id == role_id).options(joinedload(Role.permissions)))
        .scalars()
        .first()
    )
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    return success_response(
        data=[
            PermissionOut(id=permission.id, action=permission.action).model_dump()
            for permission in role.permissions
        ],
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/{role_id}/permissions/{permission_id}",
    response_model=SuccessResponse[PermissionOut],
    status_code=status.HTTP_201_CREATED,
)
def add_permission_to_role(
    role_id: int,
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    role = db.get(Role, role_id)
    permission = db.get(Permission, permission_id)
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    if permission is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="permission not found")
    if permission not in role.permissions:
        role.permissions.append(permission)
        try:
            db.commit()
            build_access_index_cache(get_redis()).invalidate_global()
            RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
        except SQLAlchemyError as e:
            db.rollback()
            raise ApiError(
                status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
            ) from e
    return success_response(
        data=PermissionOut(id=permission.id, action=permission.action).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.delete(
    "/{role_id}/permissions/{permission_id}", response_model=SuccessResponse[dict[str, int]]
)
def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    role = db.get(Role, role_id)
    permission = db.get(Permission, permission_id)
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    if permission is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="permission not found")
    if permission in role.permissions:
        role.permissions.remove(permission)
        try:
            db.commit()
            build_access_index_cache(get_redis()).invalidate_global()
            RevisionService(SqlTenantRepository(db)).bump_revision(tenant_key=DEFAULT_TENANT_KEY)
        except SQLAlchemyError as e:
            db.rollback()
            raise ApiError(
                status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
            ) from e
    return success_response(
        data={"role_id": role_id, "permission_id": permission_id},
        request_id=request_id_from_state(request.state),
    )
