"""Response helpers for standardized API envelopes."""

from __future__ import annotations

from typing import Any

from keynetra.domain.schemas.api import MetaBody


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


def request_id_from_state(state: Any) -> str | None:
    return getattr(state, "request_id", None)
