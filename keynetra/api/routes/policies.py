"""HTTP transport for policy management."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.security import get_principal
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import PolicyCreate, PolicyDslCreate, PolicyOut
from keynetra.services.policy_dsl import dsl_to_policy

router = APIRouter(prefix="/policies", dependencies=[Depends(get_principal)])


@router.get("", response_model=SuccessResponse[list[PolicyOut]])
def list_policies(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, object]:
    if limit < 1 or limit > 100:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="limit must be between 1 and 100",
        )
    tenant_key = access.tenant_key
    try:
        items, next_cursor = services.policy_service.list_policies_page(
            tenant_key=tenant_key, limit=limit, cursor=decode_cursor(cursor)
        )
        tenant = services.tenant_repo.get_or_create(tenant_key)
        warnings = services.policy_lint_service.lint(tenant_id=tenant.id)
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=[
            PolicyOut(
                id=int(cast(Any, item["id"])),
                action=str(item["action"]),
                effect=str(item["effect"]),
                priority=int(cast(Any, item["priority"])),
                state=str(item.get("state", "active")),
                conditions=cast(dict[str, object], item.get("conditions") or {}),
            ).model_dump()
            for item in items
        ],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
        meta={"warnings": warnings} if warnings else None,
    )


@router.post("", response_model=SuccessResponse[PolicyOut], status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: PolicyCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    tenant_key = access.tenant_key
    if payload.effect not in {"allow", "deny"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="effect must be allow or deny",
        )
    if payload.state not in {"draft", "active", "archived"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="state must be one of draft, active, archived",
        )
    try:
        result = services.policy_service.create_policy(
            tenant_key=tenant_key,
            policy_key=str(payload.conditions.get("policy_key") or payload.action),
            action=payload.action,
            effect=payload.effect,
            priority=payload.priority,
            conditions=payload.conditions,
            created_by=str(principal.get("id")),
            state=payload.state,
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    warnings = services.policy_lint_service.lint(
        tenant_id=services.tenant_repo.get_or_create(tenant_key).id
    )
    return success_response(
        data=PolicyOut(
            id=result.id,
            action=result.action,
            effect=result.effect,
            priority=result.priority,
            state=result.state,
            conditions=result.conditions,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
        meta={"warnings": warnings} if warnings else None,
    )


@router.put("/{policy_key}", response_model=SuccessResponse[PolicyOut])
def update_policy(
    policy_key: str,
    payload: PolicyCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    if payload.effect not in {"allow", "deny"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="effect must be allow or deny",
        )
    if payload.state not in {"draft", "active", "archived"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="state must be one of draft, active, archived",
        )
    try:
        result = services.policy_service.create_policy(
            tenant_key=access.tenant_key,
            policy_key=policy_key,
            action=payload.action,
            effect=payload.effect,
            priority=payload.priority,
            conditions=payload.conditions,
            created_by=str(principal.get("id")),
            state=payload.state,
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    warnings = services.policy_lint_service.lint(
        tenant_id=services.tenant_repo.get_or_create(access.tenant_key).id
    )
    return success_response(
        data=PolicyOut(
            id=result.id,
            action=result.action,
            effect=result.effect,
            priority=result.priority,
            state=result.state,
            conditions=result.conditions,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
        meta={"warnings": warnings} if warnings else None,
    )


@router.post("/dsl", response_model=SuccessResponse[PolicyOut], status_code=status.HTTP_201_CREATED)
def create_policy_from_dsl(
    payload: PolicyDslCreate,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    try:
        policy = dsl_to_policy(payload.dsl)
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    return create_policy(
        payload=PolicyCreate(
            action=policy["action"],
            effect=policy["effect"],
            priority=policy["priority"],
            state="active",
            conditions=policy["conditions"],
        ),
        request=request,
        services=services,
        principal=principal,
        access=access,
    )


@router.delete("/{policy_key}", response_model=SuccessResponse[dict[str, str]])
def delete_policy(
    policy_key: str,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    try:
        services.policy_service.delete_policy(tenant_key=access.tenant_key, policy_key=policy_key)
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data={"policy_key": policy_key}, request_id=request_id_from_state(request.state)
    )


@router.post(
    "/{policy_key}/rollback/{version}", response_model=SuccessResponse[dict[str, int | str]]
)
def rollback_policy(
    policy_key: str,
    version: int,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    try:
        current_policy_key, current_version = services.policy_service.rollback_policy(
            tenant_key=access.tenant_key,
            policy_key=policy_key,
            version=version,
        )
    except ValueError as error:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message=str(error)) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data={"policy_key": current_policy_key, "current_version": current_version},
        request_id=request_id_from_state(request.state),
    )
