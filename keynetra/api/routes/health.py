from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from keynetra.api.dependencies import ServiceContainer, build_services
from keynetra.api.responses import envelope_json_response, request_id_from_state, success_response
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings, get_settings
from keynetra.domain.schemas.api import SuccessResponse

router = APIRouter()


@router.get("/health", response_model=SuccessResponse[dict[str, str]])
def health(request: Request) -> dict[str, object]:
    return success_response(data={"status": "ok"}, request_id=request_id_from_state(request.state))


@router.get("/health/live", response_model=SuccessResponse[dict[str, str]])
def liveness(request: Request) -> dict[str, object]:
    return success_response(data={"status": "ok"}, request_id=request_id_from_state(request.state))


@router.get("/health/ready", response_model=SuccessResponse[dict[str, object]])
def readiness(
    request: Request,
    settings: Settings = Depends(get_settings),
    services: ServiceContainer = Depends(build_services),
) -> JSONResponse:
    database_status = _check_database(services)
    redis_status = _check_redis(settings)
    healthy = database_status["status"] == "ok" and redis_status["status"] in {
        "ok",
        "not_configured",
    }
    return envelope_json_response(
        status_code=HTTPStatus.OK if healthy else HTTPStatus.SERVICE_UNAVAILABLE,
        data={
            "status": "ok" if healthy else "degraded",
            "checks": {
                "database": database_status,
                "redis": redis_status,
            },
        },
        request_id=request_id_from_state(request.state),
    )


def _check_database(services: ServiceContainer) -> dict[str, str]:
    try:
        services.db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": repr(exc)}


def _check_redis(settings: Settings) -> dict[str, str]:
    if not settings.redis_url:
        return {"status": "not_configured"}

    client = get_redis()
    if client is None:
        return {"status": "error", "detail": "redis client unavailable"}

    try:
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "detail": repr(exc)}
