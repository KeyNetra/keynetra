"""Cursor pagination helpers for stable API list endpoints."""

from __future__ import annotations

from typing import Any

from keynetra.api.errors import ApiError, ApiErrorCode
from keynetra.domain.pagination import decode_cursor as _decode_cursor
from keynetra.domain.pagination import encode_cursor as _encode_cursor


def encode_cursor(payload: dict[str, Any]) -> str:
    return _encode_cursor(payload)


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    """Decode an opaque cursor payload or raise a validation error."""

    if not cursor:
        return None
    try:
        decoded = _decode_cursor(cursor)
    except Exception as exc:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="invalid cursor",
            details={"cursor": cursor},
        ) from exc
    return decoded
