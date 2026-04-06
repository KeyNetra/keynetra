"""HTTP transport for relationship management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.config.redis_client import get_redis
from keynetra.config.security import get_principal
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.relationship_cache import build_relationship_cache
from keynetra.infrastructure.repositories.relationships import SqlRelationshipRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.relationships import RelationshipService

router = APIRouter(prefix="/relationships", dependencies=[Depends(get_principal)])


class RelationshipCreate(BaseModel):
    subject_type: str
    subject_id: str
    relation: str
    object_type: str
    object_id: str


class RelationshipOut(RelationshipCreate):
    id: int


def get_relationship_service(db: Session = Depends(get_db)) -> RelationshipService:
    """Create the request-scoped relationship service."""

    redis_client = get_redis()
    return RelationshipService(
        tenants=SqlTenantRepository(db),
        relationships=SqlRelationshipRepository(db),
        relationship_cache=build_relationship_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
    )


@router.get("", response_model=SuccessResponse[list[dict[str, str]]])
def list_relationships(
    subject_type: str,
    subject_id: str,
    request: Request,
    service: RelationshipService = Depends(get_relationship_service),
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
    try:
        data, next_cursor = service.list_relationships_page(
            tenant_key=access.tenant_key,
            subject_type=subject_type,
            subject_id=subject_id,
            limit=limit,
            cursor=decode_cursor(cursor),
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=data,
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
    )


@router.post(
    "", response_model=SuccessResponse[RelationshipOut], status_code=status.HTTP_201_CREATED
)
def create_relationship(
    payload: RelationshipCreate,
    request: Request,
    service: RelationshipService = Depends(get_relationship_service),
    access: AdminAccess = Depends(require_management_role("developer")),
) -> dict[str, object]:
    try:
        row_id = service.create_relationship(tenant_key=access.tenant_key, **payload.model_dump())
    except IntegrityError as error:
        raise ApiError(
            status_code=409, code=ApiErrorCode.CONFLICT, message="relationship exists"
        ) from error
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=RelationshipOut(id=row_id, **payload.model_dump()).model_dump(),
        request_id=request_id_from_state(request.state),
    )
