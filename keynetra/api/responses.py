"""Response helpers for standardized API envelopes."""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from keynetra.api.errors import ApiErrorCode
from keynetra.domain.schemas.api import ErrorBody
from keynetra.domain.schemas.api import MetaBody
from keynetra.infrastructure.logging import get_request_id


def success_response(
    *,
    data: Any,
    request_id: str | None = None,
    limit: int | None = None,
    next_cursor: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "data": data,
        "meta": MetaBody(
            request_id=request_id, limit=limit, next_cursor=next_cursor, extra=meta or {}
        ).model_dump(),
        "error": None,
    }


def error_response(
    *,
    code: ApiErrorCode | str,
    message: str,
    details: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    normalized_code = _normalize_error_code(code)
    return {
        "data": None,
        "meta": MetaBody(request_id=request_id).model_dump(),
        "error": ErrorBody(code=normalized_code, message=message, details=details).model_dump(),
    }


def envelope_json_response(
    *,
    status_code: int,
    data: Any,
    request_id: str | None = None,
    limit: int | None = None,
    next_cursor: str | None = None,
    meta: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=success_response(
            data=data,
            request_id=request_id,
            limit=limit,
            next_cursor=next_cursor,
            meta=meta,
        ),
    )
    _apply_common_headers(response=response, request_id=request_id, headers=headers)
    return response


def error_json_response(
    *,
    status_code: int,
    code: ApiErrorCode | str,
    message: str,
    details: Any = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=error_response(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        ),
    )
    _apply_common_headers(response=response, request_id=request_id, headers=headers)
    return response


def ensure_request_id(request: Request) -> str:
    current = request_id_from_state(request.state)
    if current:
        return current
    request_id = request.headers.get("X-Request-Id") or get_request_id() or secrets.token_urlsafe(10)
    request.state.request_id = request_id
    return request_id


def request_id_from_state(state: Any) -> str | None:
    return getattr(state, "request_id", None) or get_request_id()


def _apply_common_headers(
    *,
    response: JSONResponse,
    request_id: str | None,
    headers: dict[str, str] | None,
) -> None:
    if request_id:
        response.headers["X-Request-Id"] = request_id
    for key, value in (headers or {}).items():
        response.headers[key] = value


def _normalize_error_code(code: ApiErrorCode | str) -> str:
    if isinstance(code, ApiErrorCode):
        return str(code)
    try:
        return str(ApiErrorCode(code))
    except ValueError as exc:
        raise ValueError(f"unknown api error code: {code}") from exc
