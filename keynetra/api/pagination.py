"""Cursor pagination helpers for stable API list endpoints."""

from __future__ import annotations

import base64
import json
from typing import Any

from keynetra.api.errors import ApiError, ApiErrorCode


def encode_cursor(payload: dict[str, Any]) -> str:
    """Encode an opaque cursor payload."""

    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    """Decode an opaque cursor payload or raise a validation error."""

    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        decoded = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="invalid cursor",
            details={"cursor": cursor},
        ) from exc
    if not isinstance(decoded, dict):
        raise ApiError(
            status_code=422,
            code=ApiErrorCode.VALIDATION_ERROR,
            message="invalid cursor",
            details={"cursor": cursor},
        )
    return decoded
