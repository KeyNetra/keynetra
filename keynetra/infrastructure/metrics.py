"""Core metrics hooks."""

from __future__ import annotations

from keynetra.observability.metrics import (  # noqa: F401
    observe_decision_latency,
    record_api_error,
    record_cache_event,
)

__all__ = [
    "observe_decision_latency",
    "record_api_error",
    "record_cache_event",
]
