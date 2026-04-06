"""HTTP transport for authorization checks.

The API layer validates transport concerns and delegates orchestration to the
service layer. It does not perform policy evaluation or persistence logic.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.redis_client import get_redis
from keynetra.config.security import get_principal
from keynetra.config.settings import Settings, get_settings
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
from keynetra.services.attribute_validation import AttributeValidationError
from keynetra.services.authorization import AuthorizationService

router = APIRouter()
logger = logging.getLogger("keynetra.access")


def get_authorization_service(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> AuthorizationService:
    """Create the request-scoped authorization service."""

    redis_client = get_redis()
    return AuthorizationService(
        settings=settings,
        tenants=SqlTenantRepository(db),
        policies=SqlPolicyRepository(db),
        users=SqlUserRepository(db),
        relationships=SqlRelationshipRepository(db),
        audit=SqlAuditRepository(db),
        policy_cache=build_policy_cache(redis_client),
        relationship_cache=build_relationship_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        acl_repository=SqlACLRepository(db),
        acl_cache=build_acl_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
        auth_model_repository=SqlAuthModelRepository(db),
    )


@router.post(
    "/check-access",
    response_model=SuccessResponse[AccessDecisionResponse],
    dependencies=[Depends(get_principal)],
)
def check_access(
    payload: AccessRequest,
    request: Request,
    service: AuthorizationService = Depends(get_authorization_service),
    principal: dict[str, str] = Depends(get_principal),
) -> dict[str, object]:
    try:
        result = service.authorize(
            tenant_key=DEFAULT_TENANT_KEY,
            principal=principal,
            user=payload.user,
            action=payload.action,
            resource=payload.resource,
            context=payload.context,
            consistency=payload.consistency,
            revision=payload.revision,
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
    service: AuthorizationService = Depends(get_authorization_service),
    principal: dict[str, str] = Depends(get_principal),
) -> dict[str, object]:
    try:
        decision = service.simulate(
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
            revision=service.get_revision(tenant_key=DEFAULT_TENANT_KEY),
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
    service: AuthorizationService = Depends(get_authorization_service),
    principal: dict[str, str] = Depends(get_principal),
) -> dict[str, object]:
    try:
        results = service.authorize_batch(
            tenant_key=DEFAULT_TENANT_KEY,
            principal=principal,
            user=payload.user,
            items=[item.model_dump() for item in payload.items],
            consistency=payload.consistency,
            revision=payload.revision,
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
