"""HTTP transport for authorization checks.

The API layer validates transport concerns and delegates orchestration to the
service layer. It does not perform policy evaluation or persistence logic.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.security import get_principal
from keynetra.config.tenancy import DEFAULT_TENANT_KEY
from keynetra.domain.schemas.access import (
    AccessDecisionResponse,
    AccessRequest,
    BatchAccessRequest,
    BatchAccessResponse,
    BatchAccessResult,
    SimulationResponse,
)
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.services.attribute_validation import AttributeValidationError
from keynetra.services.authorization import AuthorizationService

router = APIRouter()
logger = logging.getLogger("keynetra.access")


def _legacy_service_override() -> AuthorizationService | None:
    return None


@router.post(
    "/check-access",
    response_model=SuccessResponse[AccessDecisionResponse],
    dependencies=[Depends(get_principal)],
)
def check_access(
    payload: AccessRequest,
    request: Request,
    service: AuthorizationService | None = Depends(_legacy_service_override),
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
    policy_set: str = "active",
) -> dict[str, object]:
    effective_service = service or services.authorization_service
    normalized_policy_set = policy_set.strip().lower()
    if normalized_policy_set not in {"active", "draft", "archived"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="policy_set must be one of active, draft, archived",
        )
    try:
        result = effective_service.authorize(
            tenant_key=DEFAULT_TENANT_KEY,
            principal=principal,
            user=payload.user,
            action=payload.action,
            resource=payload.resource,
            context=payload.context,
            consistency=payload.consistency,
            revision=payload.revision,
            policy_set=normalized_policy_set,
        )
    except AttributeValidationError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ApiErrorCode.VALIDATION_ERROR,
            message=str(error),
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error

    logger.info(
        "decision user=%s action=%s result=%s cached=%s principal=%s",
        payload.user.get("id"),
        payload.action,
        result.decision.decision.upper(),
        result.cached,
        principal.get("type"),
    )
    return success_response(
        data=AccessDecisionResponse(
            allowed=result.decision.allowed,
            decision=result.decision.decision,
            matched_policies=list(result.decision.matched_policies),
            reason=result.decision.reason,
            policy_id=result.decision.policy_id,
            explain_trace=[step.to_dict() for step in result.decision.explain_trace],
            revision=result.revision,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/simulate",
    response_model=SuccessResponse[SimulationResponse],
    dependencies=[Depends(get_principal)],
)
def simulate(
    payload: AccessRequest,
    request: Request,
    service: AuthorizationService | None = Depends(_legacy_service_override),
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
) -> dict[str, object]:
    effective_service = service or services.authorization_service
    try:
        decision = effective_service.simulate(
            tenant_key=DEFAULT_TENANT_KEY,
            principal=principal,
            user=payload.user,
            action=payload.action,
            resource=payload.resource,
            context=payload.context,
        )
    except AttributeValidationError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ApiErrorCode.VALIDATION_ERROR,
            message=str(error),
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error

    logger.info(
        "simulate user=%s action=%s result=%s principal=%s",
        payload.user.get("id"),
        payload.action,
        decision.decision.upper(),
        principal.get("type"),
    )
    return success_response(
        data=SimulationResponse(
            decision=decision.decision,
            matched_policies=list(decision.matched_policies),
            reason=decision.reason,
            policy_id=decision.policy_id,
            explain_trace=[step.to_dict() for step in decision.explain_trace],
            failed_conditions=list(decision.failed_conditions),
            revision=effective_service.get_revision(tenant_key=DEFAULT_TENANT_KEY),
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.post(
    "/check-access-batch",
    response_model=SuccessResponse[BatchAccessResponse],
    dependencies=[Depends(get_principal)],
)
def check_access_batch(
    payload: BatchAccessRequest,
    request: Request,
    service: AuthorizationService | None = Depends(_legacy_service_override),
    services: ServiceContainer = Depends(build_services),
    principal: dict[str, str] = Depends(get_principal),
    policy_set: str = "active",
) -> dict[str, object]:
    effective_service = service or services.authorization_service
    normalized_policy_set = policy_set.strip().lower()
    if normalized_policy_set not in {"active", "draft", "archived"}:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="policy_set must be one of active, draft, archived",
        )
    try:
        results = effective_service.authorize_batch(
            tenant_key=DEFAULT_TENANT_KEY,
            principal=principal,
            user=payload.user,
            items=[item.model_dump() for item in payload.items],
            consistency=payload.consistency,
            revision=payload.revision,
            policy_set=normalized_policy_set,
        )
    except AttributeValidationError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=ApiErrorCode.VALIDATION_ERROR,
            message=str(error),
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error

    logger.info(
        "batch user=%s items=%s principal=%s",
        payload.user.get("id"),
        len(payload.items),
        principal.get("type"),
    )
    return success_response(
        data=BatchAccessResponse(
            results=[
                BatchAccessResult(
                    action=item.action, allowed=result.decision.allowed, revision=result.revision
                ).model_dump()
                for item, result in zip(payload.items, results, strict=False)
            ],
            revision=results[0].revision if results else None,
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )
