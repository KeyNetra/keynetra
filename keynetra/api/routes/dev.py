from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.sample_data import sample_bootstrap_document
from keynetra.config.settings import Settings, get_settings
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.services.seeding import seed_demo_data

router = APIRouter(prefix="/dev")


def _require_local_dev(settings: Settings) -> None:
    if settings.environment.strip().lower() not in {"development", "dev", "local"}:
        raise ApiError(status_code=404, code=ApiErrorCode.NOT_FOUND, message="not found")


@router.get("/sample-data", response_model=SuccessResponse[dict[str, object]])
def get_sample_data(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _require_local_dev(settings)
    return success_response(
        data=sample_bootstrap_document(), request_id=request_id_from_state(request.state)
    )


@router.post("/sample-data/seed", response_model=SuccessResponse[dict[str, object]])
def seed_sample_data(
    request: Request,
    services: ServiceContainer = Depends(build_services),
    settings: Settings = Depends(get_settings),
    reset: bool = Query(False, description="Clear the sample dataset before reseeding it."),
) -> dict[str, object]:
    _require_local_dev(settings)
    summary = seed_demo_data(services.db, reset=reset)
    return success_response(
        data={
            "tenant_key": summary.tenant_key,
            "created_tenant": summary.created_tenant,
            "created_user": summary.created_user,
            "created_role": summary.created_role,
            "created_permissions": summary.created_permissions,
            "created_relationships": summary.created_relationships,
            "created_policies": summary.created_policies,
        },
        request_id=request_id_from_state(request.state),
    )
