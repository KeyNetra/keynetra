"""HTTP transport for policy management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.redis_client import get_redis
from keynetra.config.security import get_principal
from keynetra.config.settings import Settings, get_settings
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import PolicyCreate, PolicyOut
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.cache.policy_distribution import RedisPolicyEventPublisher
from keynetra.infrastructure.repositories.policies import SqlPolicyRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.policies import PolicyService
from keynetra.services.policy_dsl import dsl_to_policy
from keynetra.services.policy_lint import PolicyLintService

router = APIRouter(prefix="/policies", dependencies=[Depends(get_principal)])


def get_policy_service(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> tuple[PolicyService, PolicyLintService, SqlTenantRepository]:
    """Create the shared repositories for policy management."""

    redis_client = get_redis()
    tenant_repo = SqlTenantRepository(db)
    policy_repo = SqlPolicyRepository(db)
    service = PolicyService(
        tenants=tenant_repo,
        policies=policy_repo,
        policy_cache=build_policy_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        publisher=RedisPolicyEventPublisher(settings),
    )
    lint_service = PolicyLintService(session=db, policies=policy_repo)
    return service, lint_service, tenant_repo


@router.get("", response_model=SuccessResponse[list[PolicyOut]])
def list_policies(
    request: Request,
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
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
    service, lint_service, tenant_repo = deps
    tenant_key = access.tenant_key
    try:
        items, next_cursor = service.list_policies_page(
            tenant_key=tenant_key, limit=limit, cursor=decode_cursor(cursor)
        )
        tenant = tenant_repo.get_or_create(tenant_key)
        warnings = lint_service.lint(tenant_id=tenant.id)
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=[PolicyOut(**item).model_dump() for item in items],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
        meta={"warnings": warnings} if warnings else None,
    )


@router.post("", response_model=SuccessResponse[PolicyOut], status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: PolicyCreate,
    request: Request,
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    service, lint_service, tenant_repo = deps
    tenant_key = access.tenant_key
    if payload.effect not in {"allow", "deny"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="effect must be allow or deny",
        )
    try:
        result = service.create_policy(
            tenant_key=tenant_key,
            policy_key=str(payload.conditions.get("policy_key") or payload.action),
            action=payload.action,
            effect=payload.effect,
            priority=payload.priority,
            conditions=payload.conditions,
            created_by=str(principal.get("id")),
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    warnings = lint_service.lint(tenant_id=tenant_repo.get_or_create(tenant_key).id)
    return success_response(
        data=PolicyOut(
            id=result.id,
            action=result.action,
            effect=result.effect,
            priority=result.priority,
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
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    service, lint_service, tenant_repo = deps
    if payload.effect not in {"allow", "deny"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="effect must be allow or deny",
        )
    try:
        result = service.create_policy(
            tenant_key=access.tenant_key,
            policy_key=policy_key,
            action=payload.action,
            effect=payload.effect,
            priority=payload.priority,
            conditions=payload.conditions,
            created_by=str(principal.get("id")),
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    warnings = lint_service.lint(tenant_id=tenant_repo.get_or_create(access.tenant_key).id)
    return success_response(
        data=PolicyOut(
            id=result.id,
            action=result.action,
            effect=result.effect,
            priority=result.priority,
            conditions=result.conditions,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
        meta={"warnings": warnings} if warnings else None,
    )


@router.post("/dsl", response_model=SuccessResponse[PolicyOut], status_code=status.HTTP_201_CREATED)
def create_policy_from_dsl(
    dsl: str,
    request: Request,
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
    principal: dict[str, str] = Depends(get_principal),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    try:
        policy = dsl_to_policy(dsl)
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    return create_policy(
        payload=PolicyCreate(
            action=policy["action"],
            effect=policy["effect"],
            priority=policy["priority"],
            conditions=policy["conditions"],
        ),
        request=request,
        deps=deps,
        principal=principal,
        access=access,
    )


@router.delete("/{policy_key}", response_model=SuccessResponse[dict[str, str]])
def delete_policy(
    policy_key: str,
    request: Request,
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    service, _, _ = deps
    try:
        service.delete_policy(tenant_key=access.tenant_key, policy_key=policy_key)
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
    deps: tuple[PolicyService, PolicyLintService, SqlTenantRepository] = Depends(
        get_policy_service
    ),
    access: AdminAccess = Depends(require_management_role("admin")),
) -> dict[str, object]:
    service, _, _ = deps
    try:
        current_policy_key, current_version = service.rollback_policy(
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
