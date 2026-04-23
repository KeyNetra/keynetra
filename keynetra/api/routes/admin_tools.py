from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from http import HTTPStatus
from typing import Any, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import joinedload

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor, encode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.models.acl import ResourceACL
from keynetra.domain.models.rbac import Permission, Role, User
from keynetra.domain.models.relationship import Relationship
from keynetra.domain.models.tenant import Tenant
from keynetra.domain.schemas.admin import (
    ApiKeyCreate,
    ApiKeyCreatedOut,
    ApiKeyOut,
    BulkExportOut,
    BulkImportOut,
    BulkImportRequest,
    PolicyTestResultOut,
    PolicyTestSuiteRequest,
    PolicyVersionDiffOut,
    PolicyVersionOut,
    TenantCreate,
    TenantOut,
    UserRoleAssignmentOut,
)
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import AuditRecordOut
from keynetra.infrastructure.repositories.api_keys import SqlApiKeyRepository
from keynetra.services.policy_testing import validate_policy_test_suite
from keynetra.services.revisions import RevisionService

router = APIRouter(dependencies=[Depends(get_principal)])


@router.get("/tenants", response_model=SuccessResponse[list[TenantOut]])
def list_tenants(
    request: Request,
    services: ServiceContainer = Depends(build_services),
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
    query = select(Tenant).order_by(Tenant.id.asc())
    decoded = decode_cursor(cursor)
    if decoded is not None:
        query = query.where(Tenant.id > int(decoded["id"]))
    rows = services.db.execute(query.limit(limit + 1)).scalars().all()
    has_next = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor({"id": page[-1].id}) if has_next and page else None
    return success_response(
        data=[
            TenantOut(
                id=row.id,
                tenant_key=row.tenant_key,
                policy_version=row.policy_version,
                revision=row.authorization_revision,
            ).model_dump()
            for row in page
        ],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.post("/tenants", response_model=SuccessResponse[TenantOut], status_code=HTTPStatus.CREATED)
def create_tenant(
    payload: TenantCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    existing = (
        services.db.execute(select(Tenant).where(Tenant.tenant_key == payload.tenant_key))
        .scalars()
        .first()
    )
    if existing is not None:
        raise ApiError(status_code=409, code=ApiErrorCode.CONFLICT, message="tenant already exists")
    tenant = Tenant(tenant_key=payload.tenant_key, policy_version=1, authorization_revision=1)
    try:
        services.db.add(tenant)
        services.db.commit()
        services.db.refresh(tenant)
    except SQLAlchemyError as error:
        services.db.rollback()
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=TenantOut(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version,
            revision=tenant.authorization_revision,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.get("/tenants/{tenant_key}", response_model=SuccessResponse[TenantOut])
def get_tenant(
    tenant_key: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = (
        services.db.execute(select(Tenant).where(Tenant.tenant_key == tenant_key)).scalars().first()
    )
    if tenant is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="tenant not found")
    return success_response(
        data=TenantOut(
            id=tenant.id,
            tenant_key=tenant.tenant_key,
            policy_version=tenant.policy_version,
            revision=tenant.authorization_revision,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.get("/tenants/{tenant_key}/api-keys", response_model=SuccessResponse[list[ApiKeyOut]])
def list_api_keys(
    tenant_key: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = _get_tenant_or_404(services, tenant_key)
    rows = SqlApiKeyRepository(services.db).list_keys(tenant_id=tenant.id)
    return success_response(
        data=[_api_key_out(row).model_dump() for row in rows],
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/tenants/{tenant_key}/api-keys",
    response_model=SuccessResponse[ApiKeyCreatedOut],
    status_code=HTTPStatus.CREATED,
)
def create_api_key(
    tenant_key: str,
    payload: ApiKeyCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    tenant = _get_tenant_or_404(services, tenant_key)
    scopes = payload.scopes.model_dump()
    if scopes.get("tenant") and str(scopes["tenant"]) != tenant_key:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="api key tenant scope must match the path tenant",
        )
    scopes["tenant"] = tenant_key
    scopes["role"] = str(scopes.get("role") or access.role)
    secret = _generate_api_key()
    key_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    try:
        record = SqlApiKeyRepository(services.db).create_key(
            tenant_id=tenant.id,
            name=payload.name,
            key_hash=key_hash,
            scopes=scopes,
        )
    except SQLAlchemyError as error:
        services.db.rollback()
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=ApiKeyCreatedOut(secret=secret, **_api_key_out(record).model_dump()).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.delete(
    "/tenants/{tenant_key}/api-keys/{key_id}", response_model=SuccessResponse[dict[str, int]]
)
def revoke_api_key(
    tenant_key: str,
    key_id: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    tenant = _get_tenant_or_404(services, tenant_key)
    SqlApiKeyRepository(services.db).revoke_key(tenant_id=tenant.id, key_id=key_id)
    return success_response(
        data={"api_key_id": key_id}, request_id=request_id_from_state(request.state)
    )


@router.get(
    "/users/{external_id}/roles", response_model=SuccessResponse[list[UserRoleAssignmentOut]]
)
def list_user_roles(
    external_id: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    user = _get_or_create_user(services, external_id)
    roles = [role.name for role in user.roles]
    return success_response(
        data=[
            UserRoleAssignmentOut(
                user_id=user.id, external_id=user.external_id, roles=roles
            ).model_dump()
        ],
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/users/{external_id}/roles/{role_id}", response_model=SuccessResponse[UserRoleAssignmentOut]
)
def assign_user_role(
    external_id: str,
    role_id: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    user = _get_or_create_user(services, external_id)
    role = services.db.get(Role, role_id)
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    if role not in user.roles:
        user.roles.append(role)
        try:
            services.db.commit()
        except SQLAlchemyError as error:
            services.db.rollback()
            raise ApiError(
                status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
            ) from error
    services.decision_cache.bump_namespace(access.tenant_key)
    RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
    return success_response(
        data=UserRoleAssignmentOut(
            user_id=user.id, external_id=user.external_id, roles=[item.name for item in user.roles]
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.delete(
    "/users/{external_id}/roles/{role_id}", response_model=SuccessResponse[UserRoleAssignmentOut]
)
def remove_user_role(
    external_id: str,
    role_id: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    user = _get_user_or_404(services, external_id)
    role = services.db.get(Role, role_id)
    if role is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="role not found")
    if role in user.roles:
        user.roles.remove(role)
        try:
            services.db.commit()
        except SQLAlchemyError as error:
            services.db.rollback()
            raise ApiError(
                status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
            ) from error
    services.decision_cache.bump_namespace(access.tenant_key)
    RevisionService(services.tenant_repo).bump_revision(tenant_key=access.tenant_key)
    return success_response(
        data=UserRoleAssignmentOut(
            user_id=user.id, external_id=user.external_id, roles=[item.name for item in user.roles]
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.get(
    "/policies/{policy_key}/versions",
    response_model=SuccessResponse[list[PolicyVersionOut]],
)
def list_policy_versions(
    policy_key: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(request.state.admin_tenant_key)
    versions = services.policy_repo.list_policy_versions(tenant_id=tenant.id, policy_key=policy_key)
    return success_response(
        data=[PolicyVersionOut(**version).model_dump(mode="json") for version in versions],
        request_id=request_id_from_state(request.state),
    )


@router.get(
    "/policies/{policy_key}/versions/{version}",
    response_model=SuccessResponse[PolicyVersionOut],
)
def get_policy_version(
    policy_key: str,
    version: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(request.state.admin_tenant_key)
    record = services.policy_repo.get_policy_version(
        tenant_id=tenant.id, policy_key=policy_key, version=version
    )
    if record is None:
        raise ApiError(
            status_code=404, code=ApiErrorCode.NOT_FOUND, message="policy version not found"
        )
    return success_response(
        data=PolicyVersionOut(**record).model_dump(mode="json"),
        request_id=request_id_from_state(request.state),
    )


@router.get(
    "/policies/{policy_key}/versions/{from_version}/diff/{to_version}",
    response_model=SuccessResponse[PolicyVersionDiffOut],
)
def diff_policy_versions(
    policy_key: str,
    from_version: int,
    to_version: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(request.state.admin_tenant_key)
    left = services.policy_repo.get_policy_version(
        tenant_id=tenant.id, policy_key=policy_key, version=from_version
    )
    right = services.policy_repo.get_policy_version(
        tenant_id=tenant.id, policy_key=policy_key, version=to_version
    )
    if left is None or right is None:
        raise ApiError(
            status_code=404, code=ApiErrorCode.NOT_FOUND, message="policy version not found"
        )
    fields = ("action", "effect", "priority", "state", "conditions")
    changes = {
        field: {"from": left[field], "to": right[field]}
        for field in fields
        if left[field] != right[field]
    }
    return success_response(
        data=PolicyVersionDiffOut(
            policy_key=policy_key,
            from_version=from_version,
            to_version=to_version,
            changes=changes,
        ).model_dump(mode="json"),
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/policies/{policy_key}/versions/{version}/restore",
    response_model=SuccessResponse[dict[str, int | str]],
)
def restore_policy_version(
    policy_key: str,
    version: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    current_policy_key, current_version = services.policy_service.rollback_policy(
        tenant_key=access.tenant_key, policy_key=policy_key, version=version
    )
    return success_response(
        data={"policy_key": current_policy_key, "current_version": current_version},
        request_id=request_id_from_state(request.state),
    )


@router.post("/policy-tests/run", response_model=SuccessResponse[list[PolicyTestResultOut]])
def run_policy_tests(
    payload: PolicyTestSuiteRequest,
    request: Request,
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    try:
        results = validate_policy_test_suite(payload.document)
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    return success_response(
        data=[PolicyTestResultOut(**result.__dict__).model_dump(mode="json") for result in results],
        request_id=request_id_from_state(request.state),
    )


@router.get("/audit/export", response_model=SuccessResponse[list[AuditRecordOut]])
def export_audit(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
    limit: int = 1000,
    principal_type: str | None = None,
    principal_id: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
    correlation_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, object]:
    if limit < 1 or limit > 1000:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="limit must be between 1 and 1000",
        )
    tenant = services.tenant_repo.get_or_create(request.state.admin_tenant_key)
    cursor = None
    items: list[AuditRecordOut] = []
    remaining = limit
    while remaining > 0:
        batch, cursor = services.audit_repo.list_page(
            tenant_id=tenant.id,
            limit=min(remaining, 100),
            cursor=decode_cursor(cursor),
            principal_type=principal_type,
            principal_id=principal_id,
            user_id=user_id,
            action=action,
            resource_id=resource_id,
            decision=decision,
            correlation_id=correlation_id,
            start_time=start_time,
            end_time=end_time,
        )
        if not batch:
            break
        items.extend(AuditRecordOut(**item.__dict__) for item in batch)
        remaining -= len(batch)
        if cursor is None:
            break
    return success_response(data=items, request_id=request_id_from_state(request.state))


@router.get("/bulk/export/{resource}", response_model=SuccessResponse[BulkExportOut])
def bulk_export(
    resource: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    _: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = _get_tenant_for_request(services, request.state.admin_tenant_key)
    resource_name = _normalize_resource(resource)
    data = _export_resource(services, tenant.id, resource_name)
    return success_response(
        data=BulkExportOut(resource=resource_name, data=data).model_dump(mode="json"),
        request_id=request_id_from_state(request.state),
    )


@router.post("/bulk/import", response_model=SuccessResponse[BulkImportOut])
def bulk_import(
    payload: BulkImportRequest,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    resource_name = _normalize_resource(payload.resource)
    imported = _import_resource(services, access.tenant_key, resource_name, payload.payload)
    return success_response(
        data=BulkImportOut(resource=resource_name, imported=imported).model_dump(),
        request_id=request_id_from_state(request.state),
    )


def _get_tenant_or_404(services: ServiceContainer, tenant_key: str) -> Tenant:
    tenant = (
        services.db.execute(select(Tenant).where(Tenant.tenant_key == tenant_key)).scalars().first()
    )
    if tenant is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="tenant not found")
    return tenant


def _get_tenant_for_request(services: ServiceContainer, tenant_key: str) -> Tenant:
    return _get_tenant_or_404(services, tenant_key)


def _get_or_create_user(services: ServiceContainer, external_id: str) -> User:
    user = (
        services.db.execute(select(User).where(User.external_id == external_id)).scalars().first()
    )
    if user is None:
        user = User(external_id=external_id)
        services.db.add(user)
        services.db.commit()
        services.db.refresh(user)
    return user


def _get_user_or_404(services: ServiceContainer, external_id: str) -> User:
    user = (
        services.db.execute(select(User).where(User.external_id == external_id)).scalars().first()
    )
    if user is None:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="user not found")
    return user


def _api_key_out(record) -> ApiKeyOut:
    return ApiKeyOut(
        id=record.id,
        tenant_id=record.tenant_id,
        name=record.name,
        key_prefix=record.key_hash[:12],
        scopes=record.scopes,
        created_at=record.created_at,
        revoked_at=record.revoked_at,
    )


def _generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def _normalize_resource(resource: str) -> str:
    normalized = resource.strip().lower()
    if normalized not in {"policies", "auth-model", "roles", "permissions", "acl", "relationships"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="unsupported bulk resource",
        )
    return normalized


def _export_resource(services: ServiceContainer, tenant_id: int, resource: str) -> Any:
    db = services.db
    if resource == "policies":
        return services.policy_repo.list_current_policy_views(tenant_id=tenant_id)
    if resource == "auth-model":
        record = services.auth_model_repo.get_model(tenant_id=tenant_id)
        return None if record is None else record.__dict__
    if resource == "roles":
        roles = (
            db.execute(select(Role).options(joinedload(Role.permissions)).order_by(Role.id.asc()))
            .unique()
            .scalars()
            .all()
        )
        return [
            {
                "id": role.id,
                "name": role.name,
                "permissions": [permission.action for permission in role.permissions],
            }
            for role in roles
        ]
    if resource == "permissions":
        permissions = db.execute(select(Permission).order_by(Permission.id.asc())).scalars().all()
        return [
            {
                "id": permission.id,
                "action": permission.action,
                "roles": [role.name for role in permission.roles],
            }
            for permission in permissions
        ]
    if resource == "acl":
        rows = (
            db.execute(
                select(ResourceACL)
                .where(ResourceACL.tenant_id == tenant_id)
                .order_by(ResourceACL.id.asc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": row.id,
                "subject_type": row.subject_type,
                "subject_id": row.subject_id,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "action": row.action,
                "effect": row.effect,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    relationship_rows = (
        db.execute(
            select(Relationship)
            .where(Relationship.tenant_id == tenant_id)
            .order_by(Relationship.id.asc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "subject_type": row.subject_type,
            "subject_id": row.subject_id,
            "relation": row.relation,
            "object_type": row.object_type,
            "object_id": row.object_id,
        }
        for row in relationship_rows
    ]


def _import_resource(
    services: ServiceContainer, tenant_key: str, resource: str, payload: Any
) -> int:
    tenant = services.tenant_repo.get_or_create(tenant_key)
    imported = 0
    if resource == "policies":
        if not isinstance(payload, list):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="payload must be a list",
            )
        for item in payload:
            if not isinstance(item, dict):
                continue
            conditions = dict(item.get("conditions") or {})
            policy_key = str(
                item.get("policy_key") or conditions.get("policy_key") or item.get("action")
            )
            services.policy_service.create_policy(
                tenant_key=tenant_key,
                policy_key=policy_key,
                action=str(item.get("action") or ""),
                effect=str(item.get("effect") or "deny"),
                priority=int(item.get("priority", 100)),
                conditions=conditions,
                created_by="bulk-import",
                state=str(item.get("state") or "active"),
            )
            imported += 1
        return imported
    if resource == "auth-model":
        if not isinstance(payload, dict) or not isinstance(payload.get("schema_text"), str):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="auth-model payload requires schema_text",
            )
        services.auth_model_repo.upsert_model(
            tenant_id=tenant.id,
            schema_text=payload["schema_text"],
            schema_json=dict(payload.get("schema_json") or {}),
            compiled_json=dict(payload.get("compiled_json") or {}),
        )
        return 1
    if resource == "roles":
        if not isinstance(payload, list):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="payload must be a list",
            )
        for item in payload:
            if isinstance(item, str):
                name = item
                permissions: list[Any] = []
            elif isinstance(item, dict):
                name = str(item.get("name") or "")
                permissions = cast(
                    list[Any],
                    item.get("permissions") if isinstance(item.get("permissions"), list) else [],
                )
            else:
                continue
            if not name:
                continue
            role = services.db.execute(select(Role).where(Role.name == name)).scalars().first()
            if role is None:
                role = Role(name=name)
                services.db.add(role)
                services.db.flush()
            _sync_role_permissions(services.db, role, permissions)
            imported += 1
        services.db.commit()
        services.access_index_cache.invalidate_global()
        RevisionService(services.tenant_repo).bump_revision(tenant_key=tenant_key)
        return imported
    if resource == "permissions":
        if not isinstance(payload, list):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="payload must be a list",
            )
        for item in payload:
            action = (
                item
                if isinstance(item, str)
                else item.get("action") if isinstance(item, dict) else None
            )
            if not isinstance(action, str) or not action:
                continue
            permission = (
                services.db.execute(select(Permission).where(Permission.action == action))
                .scalars()
                .first()
            )
            if permission is None:
                services.db.add(Permission(action=action))
                imported += 1
        services.db.commit()
        return imported
    if resource == "acl":
        if not isinstance(payload, list):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="payload must be a list",
            )
        for item in payload:
            if not isinstance(item, dict):
                continue
            services.acl_repo.create_acl_entry(
                tenant_id=tenant.id,
                subject_type=str(item.get("subject_type") or ""),
                subject_id=str(item.get("subject_id") or ""),
                resource_type=str(item.get("resource_type") or ""),
                resource_id=str(item.get("resource_id") or ""),
                action=str(item.get("action") or ""),
                effect=str(item.get("effect") or "deny"),
            )
            imported += 1
        services.decision_cache.bump_namespace(tenant_key)
        RevisionService(services.tenant_repo).bump_revision(tenant_key=tenant_key)
        return imported
    if resource == "relationships":
        if not isinstance(payload, list):
            raise ApiError(
                status_code=422,
                code=ApiErrorCode.VALIDATION_ERROR,
                message="payload must be a list",
            )
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                services.relationship_repo.create(
                    tenant_id=tenant.id,
                    subject_type=str(item.get("subject_type") or ""),
                    subject_id=str(item.get("subject_id") or ""),
                    relation=str(item.get("relation") or ""),
                    object_type=str(item.get("object_type") or ""),
                    object_id=str(item.get("object_id") or ""),
                )
                imported += 1
            except IntegrityError:
                services.db.rollback()
        services.decision_cache.bump_namespace(tenant_key)
        RevisionService(services.tenant_repo).bump_revision(tenant_key=tenant_key)
        return imported
    return imported


def _sync_role_permissions(db, role: Role, permissions: list[Any]) -> None:
    desired_actions = {
        str(item) if not isinstance(item, dict) else str(item.get("action") or "")
        for item in permissions
    }
    desired_actions = {action for action in desired_actions if action}
    existing = {permission.action: permission for permission in role.permissions}
    role.permissions = []
    for action in sorted(desired_actions):
        permission = existing.get(action)
        if permission is None:
            permission = (
                db.execute(select(Permission).where(Permission.action == action)).scalars().first()
            )
        if permission is None:
            permission = Permission(action=action)
            db.add(permission)
            db.flush()
        role.permissions.append(permission)
