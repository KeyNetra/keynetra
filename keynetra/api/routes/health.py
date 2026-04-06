from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from keynetra.api.responses import request_id_from_state, success_response
from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings, get_settings
from keynetra.domain.schemas.api import SuccessResponse
from keynetra.infrastructure.storage.session import create_engine_for_url

router = APIRouter()


@router.get("/health", response_model=SuccessResponse[dict[str, str]])
def health(request: Request) -> dict[str, object]:
    return success_response(data={"status": "ok"}, request_id=request_id_from_state(request.state))


@router.get("/health/live", response_model=SuccessResponse[dict[str, str]])
def liveness(request: Request) -> dict[str, object]:
    return success_response(data={"status": "ok"}, request_id=request_id_from_state(request.state))


@router.get("/health/ready", response_model=SuccessResponse[dict[str, object]])
def readiness(request: Request, settings: Settings = Depends(get_settings)) -> JSONResponse:
    database_status = _check_database(settings)
    redis_status = _check_redis(settings)
    healthy = database_status["status"] == "ok" and redis_status["status"] in {
        "ok",
        "not_configured",
    }
    payload = success_response(
        data={
            "status": "ok" if healthy else "degraded",
            "checks": {
                "database": database_status,
                "redis": redis_status,
            },
        },
        request_id=request_id_from_state(request.state),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload,
    )


def _check_database(settings: Settings) -> dict[str, str]:
    try:
        engine = create_engine_for_url(settings.database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
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
