"""HTTP request metrics helpers."""

from __future__ import annotations

import importlib
from typing import Any

try:
    _prometheus_client: Any | None = importlib.import_module("prometheus_client")
except ModuleNotFoundError:  # pragma: no cover
    _prometheus_client = None

MetricFactory = Any
Metric = Any

_counter_factory: MetricFactory | None = (
    None if _prometheus_client is None else getattr(_prometheus_client, "Counter", None)
)
_histogram_factory: MetricFactory | None = (
    None if _prometheus_client is None else getattr(_prometheus_client, "Histogram", None)
)

HTTP_REQUESTS_TOTAL: Metric | None
HTTP_REQUEST_DURATION_SECONDS: Metric | None

if _counter_factory is not None and _histogram_factory is not None:
    HTTP_REQUESTS_TOTAL = _counter_factory(
        "keynetra_http_requests_total",
        "HTTP request count",
        labelnames=("tenant", "endpoint", "method", "status"),
    )
    HTTP_REQUEST_DURATION_SECONDS = _histogram_factory(
        "keynetra_http_request_duration_seconds",
        "HTTP request latency in seconds",
        labelnames=("tenant", "endpoint", "method", "status"),
    )
else:  # pragma: no cover
    HTTP_REQUESTS_TOTAL = None
    HTTP_REQUEST_DURATION_SECONDS = None


def record_http_request(
    *, tenant: str, endpoint: str, method: str, status: int, duration_seconds: float
) -> None:
    tenant_label = str(tenant or "unknown").strip() or "unknown"
    endpoint_label = str(endpoint or "/").strip() or "/"
    method_label = str(method or "GET").strip().upper() or "GET"
    status_label = str(int(status))

    if HTTP_REQUESTS_TOTAL is not None:
        HTTP_REQUESTS_TOTAL.labels(
            tenant=tenant_label,
            endpoint=endpoint_label,
            method=method_label,
            status=status_label,
        ).inc()
    if HTTP_REQUEST_DURATION_SECONDS is not None:
        HTTP_REQUEST_DURATION_SECONDS.labels(
            tenant=tenant_label,
            endpoint=endpoint_label,
            method=method_label,
            status=status_label,
        ).observe(max(0.0, float(duration_seconds)))
