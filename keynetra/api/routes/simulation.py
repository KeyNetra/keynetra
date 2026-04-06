from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import get_settings
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.modeling import (
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    PolicySimulationRequest,
    PolicySimulationResponse,
)
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.cache.acl_cache import build_acl_cache
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.cache.relationship_cache import build_relationship_cache
from keynetra.infrastructure.repositories.acl import SqlACLRepository
from keynetra.infrastructure.repositories.audit import SqlAuditRepository
from keynetra.infrastructure.repositories.auth_models import SqlAuthModelRepository
from keynetra.infrastructure.repositories.policies import SqlPolicyRepository
from keynetra.infrastructure.repositories.relationships import SqlRelationshipRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.repositories.users import SqlUserRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.authorization import AuthorizationService
from keynetra.services.impact_analysis import ImpactAnalyzer
from keynetra.services.policy_simulator import PolicySimulator

router = APIRouter()


def get_simulation_services(
    db: Session = Depends(get_db),
) -> tuple[AuthorizationService, PolicySimulator, ImpactAnalyzer]:
    redis_client = get_redis()
    tenants = SqlTenantRepository(db)
    policies = SqlPolicyRepository(db)
    users = SqlUserRepository(db)
    relationships = SqlRelationshipRepository(db)
    auth = AuthorizationService(
        settings=get_settings(),
        tenants=tenants,
        policies=policies,
        users=users,
        relationships=relationships,
        audit=SqlAuditRepository(db),
        policy_cache=build_policy_cache(redis_client),
        relationship_cache=build_relationship_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        acl_repository=SqlACLRepository(db),
        acl_cache=build_acl_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
        auth_model_repository=SqlAuthModelRepository(db),
    )
    simulator = PolicySimulator(tenants=tenants, policies=policies, authorization_service=auth)
    impact = ImpactAnalyzer(
        tenants=tenants, policies=policies, users=users, relationships=relationships
    )
    return auth, simulator, impact


@router.post("/simulate-policy", response_model=SuccessResponse[PolicySimulationResponse])
def simulate_policy(
    payload: PolicySimulationRequest,
    request: Request,
    deps: tuple[AuthorizationService, PolicySimulator, ImpactAnalyzer] = Depends(
        get_simulation_services
    ),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    _auth, simulator, _impact = deps
    req = _normalize_request(payload.request)
    policy_change = payload.simulate.policy_change
    if not policy_change:
        raise ApiError(
            status_code=422, code=ApiErrorCode.VALIDATION_ERROR, message="policy_change is required"
        )
    try:
        result = simulator.simulate_policy_change(
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
    deps: tuple[AuthorizationService, PolicySimulator, ImpactAnalyzer] = Depends(
        get_simulation_services
    ),
    access: AdminAccess = Depends(require_management_role("viewer")),
) -> dict[str, object]:
    _auth, _simulator, impact = deps
    try:
        result = impact.analyze_policy_change(
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


def _normalize_request(raw: dict[str, object]) -> dict[str, object]:
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
    return {"user": user, "resource": resource, "action": action, "context": context}
