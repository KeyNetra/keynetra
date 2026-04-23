from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import ACLCreate, ACLOut
from keynetra.services.revisions import RevisionService

router = APIRouter(prefix="/acl", dependencies=[Depends(get_principal)])


@router.post("", response_model=SuccessResponse[ACLOut], status_code=HTTPStatus.CREATED)
def create_acl_entry(
    payload: ACLCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    if payload.effect not in {"allow", "deny"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="effect must be allow or deny",
        )
    try:
        acl_id = services.acl_repo.create_acl_entry(
            tenant_id=tenant.id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            action=payload.action,
            effect=payload.effect,
        )
        created = services.acl_repo.get_acl_entry(tenant_id=tenant.id, acl_id=acl_id)
        services.access_indexer.invalidate_resource(
            tenant_id=tenant.id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
        )
        services.decision_cache.bump_namespace(tenant.tenant_key)
        RevisionService(services.tenant_repo).bump_revision(tenant_key=tenant.tenant_key)
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=ACLOut(
            id=acl_id,
            tenant_id=tenant.id,
            created_at=None if created is None else created.created_at,
            **payload.model_dump(),
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.get("/{resource_type}/{resource_id}", response_model=SuccessResponse[list[ACLOut]])
def list_acl_entries(
    resource_type: str,
    resource_id: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    try:
        rows = services.acl_repo.list_resource_acl(
            tenant_id=tenant.id, resource_type=resource_type, resource_id=resource_id
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=[
            ACLOut(
                id=row.id,
                tenant_id=row.tenant_id,
                subject_type=row.subject_type,
                subject_id=row.subject_id,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                action=row.action,
                effect=row.effect,
                created_at=row.created_at,
            ).model_dump()
            for row in rows
        ],
        request_id=request_id_from_state(request.state),
    )


@router.delete("/{acl_id}", response_model=SuccessResponse[dict[str, int]])
def delete_acl_entry(
    acl_id: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    try:
        target = services.acl_repo.get_acl_entry(tenant_id=tenant.id, acl_id=acl_id)
        services.acl_repo.delete_acl_entry(tenant_id=tenant.id, acl_id=acl_id)
        if target is not None:
            services.access_indexer.invalidate_resource(
                tenant_id=tenant.id,
                resource_type=target.resource_type,
                resource_id=target.resource_id,
            )
        services.decision_cache.bump_namespace(tenant.tenant_key)
        RevisionService(services.tenant_repo).bump_revision(tenant_key=tenant.tenant_key)
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data={"acl_id": acl_id}, request_id=request_id_from_state(request.state)
    )
