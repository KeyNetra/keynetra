"""Structured logging helpers for core."""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from keynetra.utils.datetime import isoformat_z

_correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "keynetra_correlation_id",
    default=None,
)
_request_id_ctx: ContextVar[str | None] = ContextVar(
    "keynetra_request_id",
    default=None,
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any]
        if isinstance(record.msg, dict):
            payload = dict(record.msg)
        else:
            payload = {"message": record.getMessage()}
        payload.setdefault("timestamp", isoformat_z(datetime.now(UTC)))
        payload.setdefault("level", record.levelname)
        payload.setdefault("logger", record.name)
        return json.dumps(payload, default=str)


def configure_json_logging() -> None:
    mode = os.getenv("KEYNETRA_LOG_FORMAT", "json").strip().lower()
    if mode == "rich":
        configure_rich_logging()
        return
    root = logging.getLogger()
    if getattr(root, "_keynetra_json_logging", False):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    preserved = [
        existing
        for existing in root.handlers
        if existing.__class__.__module__.startswith("_pytest.")
    ]
    root.handlers = [*preserved, handler]
    root.setLevel(logging.INFO)
    root._keynetra_json_logging = True  # type: ignore[attr-defined]


def configure_rich_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_keynetra_rich_logging", False):
        return
    try:
        from rich.console import Console
        from rich.logging import RichHandler
    except ModuleNotFoundError:
        fallback_handler = logging.StreamHandler()
        fallback_handler.setFormatter(JsonLogFormatter())
        preserved = [
            existing
            for existing in root.handlers
            if existing.__class__.__module__.startswith("_pytest.")
        ]
        root.handlers = [*preserved, fallback_handler]
        root.setLevel(logging.INFO)
        root._keynetra_json_logging = True  # type: ignore[attr-defined]
        return

    force_color = os.getenv("KEYNETRA_FORCE_COLOR", "1").strip().lower() not in {"0", "false", "no"}
    console = Console(
        force_terminal=force_color, color_system="truecolor" if force_color else "auto"
    )
    handler: logging.Handler = RichHandler(
        rich_tracebacks=True,
        markup=True,
        show_path=False,
        console=console,
    )
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    preserved = [
        existing
        for existing in root.handlers
        if existing.__class__.__module__.startswith("_pytest.")
    ]
    root.handlers = [*preserved, handler]
    root.setLevel(logging.INFO)
    root._keynetra_rich_logging = True  # type: ignore[attr-defined]


def log_event(logger: logging.Logger, *, event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    payload.setdefault("correlation_id", get_correlation_id())
    logger.info(payload)


def set_correlation_id(correlation_id: str | None) -> Token[str | None]:
    return _correlation_id_ctx.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    _correlation_id_ctx.reset(token)


def get_correlation_id() -> str | None:
    return _correlation_id_ctx.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id_ctx.reset(token)


def get_request_id() -> str | None:
    return _request_id_ctx.get()
