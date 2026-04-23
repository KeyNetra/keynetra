from __future__ import annotations

from typing import Any, TypedDict, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.modeling import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    PolicySimulationRequest,
    PolicySimulationResponse,
)

router = APIRouter()


class _SimulationNormalizedRequest(TypedDict):
    user: dict[str, Any]
    resource: dict[str, Any]
    action: str
    context: dict[str, Any]


@router.post("/simulate-policy", response_model=SuccessResponse[PolicySimulationResponse])
def simulate_policy(
    payload: PolicySimulationRequest,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    req = _normalize_request(payload.request)
    policy_change = payload.simulate.policy_change
    if not policy_change:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message="policy_change is required"
        )
    try:
        result = services.policy_simulator.simulate_policy_change(
            tenant_key=access.tenant_key,
            user=req["user"],
            action=req["action"],
            resource=req["resource"],
            context=req["context"],
            policy_change=policy_change,
        )
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=PolicySimulationResponse(
            decision_before={
                "allowed": result.decision_before.allowed,
                "decision": result.decision_before.decision,
                "reason": result.decision_before.reason,
                "policy_id": result.decision_before.policy_id,
            },
            decision_after={
                "allowed": result.decision_after.allowed,
                "decision": result.decision_after.decision,
                "reason": result.decision_after.reason,
                "policy_id": result.decision_after.policy_id,
            },
        ).model_dump(),
        request_id=request_id_from_state(request.state),
    )


@router.post("/impact-analysis", response_model=SuccessResponse[ImpactAnalysisResponse])
def impact_analysis(
    payload: ImpactAnalysisRequest,
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    try:
        result = services.impact_analyzer.analyze_policy_change(
            tenant_key=access.tenant_key, policy_change=payload.policy_change
        )
    except ValueError as error:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message=str(error)
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=ImpactAnalysisResponse(**result.__dict__).model_dump(),
        request_id=request_id_from_state(request.state),
    )


def _normalize_request(raw: dict[str, object]) -> _SimulationNormalizedRequest:
    user = raw.get("user")
    resource = raw.get("resource")
    action = raw.get("action")
    context = raw.get("context") or {}
    if isinstance(user, str):
        user = {"id": user}
    if isinstance(resource, str):
        parts = resource.split(":", 1)
        resource = {
            "resource_type": parts[0],
            "resource_id": parts[1] if len(parts) > 1 else parts[0],
        }
    if not isinstance(user, dict):
        user = {}
    if not isinstance(resource, dict):
        resource = {}
    if not isinstance(action, str):
        action = ""
    if not isinstance(context, dict):
        context = {}
    return {
        "user": cast(dict[str, Any], user),
        "resource": cast(dict[str, Any], resource),
        "action": action,
        "context": cast(dict[str, Any], context),
    }
