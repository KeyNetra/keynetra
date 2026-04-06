"""API-layer idempotency handling for targeted write endpoints."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from keynetra.api.responses import request_id_from_state
from keynetra.config.settings import Settings
from keynetra.infrastructure.repositories.idempotency import SqlIdempotencyRepository
from keynetra.infrastructure.storage.session import create_session_factory, initialize_database


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Replays the first completed response for duplicate write requests."""

    _target_paths = {
        ("POST", "/policies"),
        ("POST", "/policies/dsl"),
        ("POST", "/relationships"),
    }

    def __init__(self, app, settings: Settings) -> None:  # type: ignore[override]
        super().__init__(app)
        initialize_database(settings.database_url)
        self._session_factory = create_session_factory(settings.database_url)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if (request.method.upper(), request.url.path) not in self._target_paths:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        body = await request.body()
        scope = f"{request.method.upper()}:{request.url.path}"
        request_hash = hashlib.sha256(b"\n".join([scope.encode("utf-8"), body])).hexdigest()

        db = self._session_factory()
        try:
            repository = SqlIdempotencyRepository(db)
            start = repository.start(
                scope=scope, idempotency_key=idempotency_key, request_hash=request_hash
            )
            if start.outcome == "mismatch":
                return JSONResponse(
                    status_code=409,
                    content={
                        "data": None,
                        "error": {
                            "code": "conflict",
                            "message": "idempotency key reused with a different request",
                            "details": {"idempotency_key": idempotency_key},
                        },
                    },
                )
            if start.outcome == "pending":
                return JSONResponse(
                    status_code=409,
                    content={
                        "data": None,
                        "error": {
                            "code": "conflict",
                            "message": "request with this idempotency key is still in progress",
                            "details": {"idempotency_key": idempotency_key},
                        },
                    },
                )
            if start.outcome == "replay":
                response = Response(
                    content=start.response_body or "",
                    status_code=start.status_code or 200,
                    media_type=start.content_type or "application/json",
                )
                response.headers["X-Idempotent-Replayed"] = "true"
                response.headers["X-Idempotency-Key"] = idempotency_key
                return response
        finally:
            db.close()

        response = await call_next(request)
        response_body = await _collect_body(response)
        replayable = _clone_response(response=response, body=response_body)
        if start.record_id is not None and response.status_code < 500:
            db = self._session_factory()
            try:
                SqlIdempotencyRepository(db).complete(
                    record_id=start.record_id,
                    status_code=response.status_code,
                    response_body=response_body.decode("utf-8"),
                    content_type=response.media_type,
                )
            finally:
                db.close()
        replayable.headers["X-Idempotency-Key"] = idempotency_key
        replayable.headers["X-Request-Id"] = request_id_from_state(
            request.state
        ) or replayable.headers.get("X-Request-Id", "")
        return replayable


async def _collect_body(response: Response) -> bytes:
    if hasattr(response, "body") and response.body is not None:
        return bytes(response.body)
    body = b""
    async for chunk in response.body_iterator:
        body += chunk
    return body


def _clone_response(*, response: Response, body: bytes) -> Response:
    headers = dict(response.headers)
    return Response(
        content=body,
        status_code=response.status_code,
        headers=headers,
        media_type=response.media_type,
        background=response.background,
    )
