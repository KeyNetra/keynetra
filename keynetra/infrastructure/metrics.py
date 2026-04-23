"""Core metrics hooks."""

from __future__ import annotations

from keynetra.observability.metrics import (  # noqa: F401
    observe_decision_latency,
    observe_resilience_executor_pressure,
    record_api_error,
    record_auth_fail_closed,
    record_auth_fail_open,
    record_backend_timeout,
    record_cache_event,
)

__all__ = [
    "observe_decision_latency",
    "observe_resilience_executor_pressure",
    "record_api_error",
    "record_auth_fail_closed",
    "record_auth_fail_open",
    "record_backend_timeout",
    "record_cache_event",
]
