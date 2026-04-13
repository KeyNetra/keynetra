from __future__ import annotations

import json
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.api.responses import error_json_response
from keynetra.config.settings import Settings
from keynetra.config.tenancy import tenant_for_logs
from keynetra.infrastructure.logging import log_event
from keynetra.infrastructure.metrics import record_api_error


def _request_id(request: Request) -> str | None:
    return getattr(getattr(request, "state", None), "request_id", None)


def register_error_handlers(app: FastAPI, settings: Settings) -> None:
    logger = logging.getLogger("keynetra.errors")

    @app.exception_handler(ApiError)
    async def api_exception_handler(request: Request, exc: ApiError):
        record_api_error(code=str(exc.code))
        log_event(
            logger,
            event="api_error",
            code=str(exc.code),
            message=exc.message,
            request_id=_request_id(request),
            tenant_id=tenant_for_logs(request),
        )
        return error_json_response(
            status_code=exc.status_code,
            code=str(exc.code),
            message=exc.message,
            details=exc.details,
            request_id=_request_id(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code_map = {
            400: ApiErrorCode.BAD_REQUEST,
            401: ApiErrorCode.UNAUTHORIZED,
            403: ApiErrorCode.FORBIDDEN,
            404: ApiErrorCode.NOT_FOUND,
            409: ApiErrorCode.CONFLICT,
            429: ApiErrorCode.TOO_MANY_REQUESTS,
        }
        code = str(code_map.get(exc.status_code, ApiErrorCode.BAD_REQUEST))
        record_api_error(code=code)
        return error_json_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            details=None,
            request_id=_request_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        record_api_error(code=str(ApiErrorCode.VALIDATION_ERROR))
        return error_json_response(
            status_code=422,
            code=str(ApiErrorCode.VALIDATION_ERROR),
            message="invalid request",
            details=exc.errors(),
            request_id=_request_id(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = _request_id(request)
        record_api_error(code=str(ApiErrorCode.INTERNAL_ERROR))
        log_event(
            logger,
            event="unhandled_exception",
            request_id=rid,
            tenant_id=tenant_for_logs(request),
            error=repr(exc),
            traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
        response = error_json_response(
            status_code=500,
            code=str(ApiErrorCode.INTERNAL_ERROR),
            message="internal server error",
            details=None,
            request_id=rid,
        )
        if settings.debug:
            body = json.loads(response.body.decode("utf-8"))
            body["error"]["details"] = repr(exc)
            response.body = json.dumps(body).encode("utf-8")
            response.headers["content-length"] = str(len(response.body))
        return response
