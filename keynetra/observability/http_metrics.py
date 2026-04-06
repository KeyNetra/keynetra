"""HTTP request metrics helpers."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram
except ModuleNotFoundError:  # pragma: no cover
    Counter = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]

if Counter is not None and Histogram is not None:
    HTTP_REQUESTS_TOTAL = Counter(
        "keynetra_http_requests_total",
        "HTTP request count",
        labelnames=("tenant", "endpoint", "method", "status"),
    )
    HTTP_REQUEST_DURATION_SECONDS = Histogram(
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
