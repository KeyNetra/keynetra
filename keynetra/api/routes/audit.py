from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.pagination import decode_cursor
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.admin_auth import AdminAccess, require_management_role
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.domain.schemas.management import AuditRecordOut

router = APIRouter(prefix="/audit")


@router.get("", response_model=SuccessResponse[list[AuditRecordOut]])
def list_audit_logs(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    access: AdminAccess = Depends(require_management_role("viewer")),
    limit: int = 50,
    cursor: str | None = None,
    user_id: str | None = None,
    resource_id: str | None = None,
    decision: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, object]:
    if limit < 1 or limit > 100:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="limit must be between 1 and 100",
        )
    tenant = services.tenant_repo.get_or_create(access.tenant_key)
    try:
        items, next_cursor = services.audit_repo.list_page(
            tenant_id=tenant.id,
            limit=limit,
            cursor=decode_cursor(cursor),
            user_id=user_id,
            resource_id=resource_id,
            decision=decision,
            start_time=start_time,
            end_time=end_time,
        )
    except SQLAlchemyError as error:
        raise ApiError(
            status_code=500, code=ApiErrorCode.DATABASE_ERROR, message="db error"
        ) from error
    return success_response(
        data=[AuditRecordOut(**item.__dict__).model_dump(mode="json") for item in items],
        request_id=request_id_from_state(request.state),
        limit=limit,
        next_cursor=next_cursor,
    )
