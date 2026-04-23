"""Prometheus metrics for KeyNetra observability."""

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
_gauge_factory: MetricFactory | None = (
    None if _prometheus_client is None else getattr(_prometheus_client, "Gauge", None)
)
_histogram_factory: MetricFactory | None = (
    None if _prometheus_client is None else getattr(_prometheus_client, "Histogram", None)
)

ACCESS_CHECKS_TOTAL: Metric | None
ACL_MATCHES_TOTAL: Metric | None
POLICY_EVALUATIONS_TOTAL: Metric | None
RELATIONSHIP_TRAVERSALS_TOTAL: Metric | None
POLICY_COMPILATIONS_TOTAL: Metric | None
REVISION_UPDATES_TOTAL: Metric | None
ACCESS_CHECK_LATENCY_SECONDS: Metric | None
CACHE_HITS_TOTAL: Metric | None
CACHE_MISSES_TOTAL: Metric | None
DECISION_LATENCY_SECONDS: Metric | None
CACHE_EVENTS_TOTAL: Metric | None
API_ERRORS_TOTAL: Metric | None
BOOTSTRAP_FAILURES_TOTAL: Metric | None
CACHE_FALLBACK_TOTAL: Metric | None
AUTH_FAILURES_TOTAL: Metric | None
JWKS_FETCH_TOTAL: Metric | None
ACCESS_INDEX_REBUILDS_TOTAL: Metric | None
DB_QUERY_LATENCY_SECONDS: Metric | None
AUTH_FAIL_OPEN_TOTAL: Metric | None
AUTH_FAIL_CLOSED_TOTAL: Metric | None
BACKEND_TIMEOUT_TOTAL: Metric | None
RESILIENCE_EXECUTOR_QUEUE_DEPTH: Metric | None

if _counter_factory is not None and _histogram_factory is not None and _gauge_factory is not None:
    ACCESS_CHECKS_TOTAL = _counter_factory(
        "keynetra_access_checks_total",
        "Authorization decision counts",
        labelnames=("tenant", "decision"),
    )
    ACL_MATCHES_TOTAL = _counter_factory(
        "keynetra_acl_matches_total",
        "ACL match counts",
        labelnames=("tenant",),
    )
    POLICY_EVALUATIONS_TOTAL = _counter_factory(
        "keynetra_policy_evaluations_total",
        "Policy evaluation counts",
        labelnames=("tenant",),
    )
    RELATIONSHIP_TRAVERSALS_TOTAL = _counter_factory(
        "keynetra_relationship_traversals_total",
        "Relationship traversal counts",
        labelnames=("tenant",),
    )
    POLICY_COMPILATIONS_TOTAL = _counter_factory(
        "keynetra_policy_compilations_total",
        "Policy compilation counts",
        labelnames=("tenant",),
    )
    REVISION_UPDATES_TOTAL = _counter_factory(
        "keynetra_revision_updates_total",
        "Revision update counts",
        labelnames=("tenant",),
    )
    ACCESS_CHECK_LATENCY_SECONDS = _histogram_factory(
        "keynetra_access_check_latency_seconds",
        "Authorization latency per evaluation stage",
        labelnames=("tenant", "stage"),
    )
    CACHE_HITS_TOTAL = _counter_factory(
        "keynetra_cache_hits_total",
        "Cache hit counts",
        labelnames=("cache_type",),
    )
    CACHE_MISSES_TOTAL = _counter_factory(
        "keynetra_cache_misses_total",
        "Cache miss counts",
        labelnames=("cache_type",),
    )
    DECISION_LATENCY_SECONDS = _histogram_factory(
        "keynetra_decision_latency_seconds",
        "Authorization decision latency",
        labelnames=("tenant_key",),
    )
    CACHE_EVENTS_TOTAL = _counter_factory(
        "keynetra_cache_events_total",
        "Authorization cache hit and miss counts",
        labelnames=("cache_name", "outcome"),
    )
    API_ERRORS_TOTAL = _counter_factory(
        "keynetra_api_errors_total",
        "Core API error counts",
        labelnames=("code",),
    )
    BOOTSTRAP_FAILURES_TOTAL = _counter_factory(
        "keynetra_bootstrap_failures_total",
        "Startup/bootstrap failure counts",
        labelnames=("stage",),
    )
    CACHE_FALLBACK_TOTAL = _counter_factory(
        "keynetra_cache_fallback_total",
        "Cache fallback counts",
        labelnames=("cache_name",),
    )
    AUTH_FAILURES_TOTAL = _counter_factory(
        "keynetra_auth_failures_total",
        "Authentication failure counts",
        labelnames=("reason",),
    )
    JWKS_FETCH_TOTAL = _counter_factory(
        "keynetra_jwks_fetch_total",
        "JWKS fetch outcome counts",
        labelnames=("outcome",),
    )
    ACCESS_INDEX_REBUILDS_TOTAL = _counter_factory(
        "keynetra_access_index_rebuilds_total",
        "Access index rebuild counts",
        labelnames=("mode",),
    )
    DB_QUERY_LATENCY_SECONDS = _histogram_factory(
        "keynetra_db_query_latency_seconds",
        "Database query latency",
        labelnames=("operation",),
    )
    AUTH_FAIL_OPEN_TOTAL = _counter_factory(
        "keynetra_auth_fail_open_total",
        "Authorization fail-open fallback count",
    )
    AUTH_FAIL_CLOSED_TOTAL = _counter_factory(
        "keynetra_auth_fail_closed_total",
        "Authorization fail-closed fallback count",
    )
    BACKEND_TIMEOUT_TOTAL = _counter_factory(
        "keynetra_backend_timeout_total",
        "Backend timeout count",
        labelnames=("operation",),
    )
    RESILIENCE_EXECUTOR_QUEUE_DEPTH = _gauge_factory(
        "keynetra_resilience_executor_queue_depth",
        "Approximate resilience executor queue depth",
    )
else:  # pragma: no cover
    ACCESS_CHECKS_TOTAL = None
    ACL_MATCHES_TOTAL = None
    POLICY_EVALUATIONS_TOTAL = None
    RELATIONSHIP_TRAVERSALS_TOTAL = None
    POLICY_COMPILATIONS_TOTAL = None
    REVISION_UPDATES_TOTAL = None
    ACCESS_CHECK_LATENCY_SECONDS = None
    CACHE_HITS_TOTAL = None
    CACHE_MISSES_TOTAL = None
    DECISION_LATENCY_SECONDS = None
    CACHE_EVENTS_TOTAL = None
    API_ERRORS_TOTAL = None
    BOOTSTRAP_FAILURES_TOTAL = None
    CACHE_FALLBACK_TOTAL = None
    AUTH_FAILURES_TOTAL = None
    JWKS_FETCH_TOTAL = None
    ACCESS_INDEX_REBUILDS_TOTAL = None
    DB_QUERY_LATENCY_SECONDS = None
    AUTH_FAIL_OPEN_TOTAL = None
    AUTH_FAIL_CLOSED_TOTAL = None
    BACKEND_TIMEOUT_TOTAL = None
    RESILIENCE_EXECUTOR_QUEUE_DEPTH = None


def _tenant_label(tenant: str | None) -> str:
    value = str(tenant or "default").strip()
    return value or "default"


def _cache_type_label(cache_type: str) -> str:
    value = str(cache_type or "unknown").strip().lower()
    return (
        value
        if value in {"policy", "acl", "relationship", "access_index", "decision"}
        else "unknown"
    )


def record_access_check(*, tenant: str | None, decision: str) -> None:
    if ACCESS_CHECKS_TOTAL is not None:
        ACCESS_CHECKS_TOTAL.labels(tenant=_tenant_label(tenant), decision=str(decision)).inc()


def record_acl_match(*, tenant: str | None) -> None:
    if ACL_MATCHES_TOTAL is not None:
        ACL_MATCHES_TOTAL.labels(tenant=_tenant_label(tenant)).inc()


def record_policy_evaluation(*, tenant: str | None) -> None:
    if POLICY_EVALUATIONS_TOTAL is not None:
        POLICY_EVALUATIONS_TOTAL.labels(tenant=_tenant_label(tenant)).inc()


def record_relationship_traversal(*, tenant: str | None) -> None:
    if RELATIONSHIP_TRAVERSALS_TOTAL is not None:
        RELATIONSHIP_TRAVERSALS_TOTAL.labels(tenant=_tenant_label(tenant)).inc()


def record_policy_compilation(*, tenant: str | None) -> None:
    if POLICY_COMPILATIONS_TOTAL is not None:
        POLICY_COMPILATIONS_TOTAL.labels(tenant=_tenant_label(tenant)).inc()


def record_revision_update(*, tenant: str | None) -> None:
    if REVISION_UPDATES_TOTAL is not None:
        REVISION_UPDATES_TOTAL.labels(tenant=_tenant_label(tenant)).inc()


def observe_access_check_latency(*, tenant: str | None, stage: str, value: float) -> None:
    if ACCESS_CHECK_LATENCY_SECONDS is not None:
        ACCESS_CHECK_LATENCY_SECONDS.labels(tenant=_tenant_label(tenant), stage=str(stage)).observe(
            value
        )


def record_cache_hit(*, cache_type: str) -> None:
    cache = _cache_type_label(cache_type)
    if CACHE_HITS_TOTAL is not None:
        CACHE_HITS_TOTAL.labels(cache_type=cache).inc()


def record_cache_miss(*, cache_type: str) -> None:
    cache = _cache_type_label(cache_type)
    if CACHE_MISSES_TOTAL is not None:
        CACHE_MISSES_TOTAL.labels(cache_type=cache).inc()


def record_cache_event(*, cache_name: str, outcome: str) -> None:
    cache = _cache_type_label(cache_name)
    outcome_label = str(outcome).strip().lower()
    if CACHE_EVENTS_TOTAL is not None:
        CACHE_EVENTS_TOTAL.labels(cache_name=cache, outcome=outcome_label or "miss").inc()
    if cache == "unknown":
        return
    if outcome_label == "hit":
        record_cache_hit(cache_type=cache)
    else:
        record_cache_miss(cache_type=cache)
    if outcome_label == "fallback" and CACHE_FALLBACK_TOTAL is not None:
        CACHE_FALLBACK_TOTAL.labels(cache_name=cache).inc()


def observe_decision_latency(*, tenant_key: str, value: float) -> None:
    if DECISION_LATENCY_SECONDS is not None:
        DECISION_LATENCY_SECONDS.labels(tenant_key=tenant_key).observe(value)


def record_api_error(*, code: str) -> None:
    if API_ERRORS_TOTAL is not None:
        API_ERRORS_TOTAL.labels(code=code).inc()


def record_bootstrap_failure(*, stage: str) -> None:
    if BOOTSTRAP_FAILURES_TOTAL is not None:
        BOOTSTRAP_FAILURES_TOTAL.labels(stage=str(stage)).inc()


def record_auth_failure(*, reason: str) -> None:
    if AUTH_FAILURES_TOTAL is not None:
        AUTH_FAILURES_TOTAL.labels(reason=str(reason)).inc()


def record_jwks_fetch(*, outcome: str) -> None:
    if JWKS_FETCH_TOTAL is not None:
        JWKS_FETCH_TOTAL.labels(outcome=str(outcome)).inc()


def record_access_index_rebuild(*, mode: str) -> None:
    if ACCESS_INDEX_REBUILDS_TOTAL is not None:
        ACCESS_INDEX_REBUILDS_TOTAL.labels(mode=str(mode)).inc()


def observe_db_query_latency(*, operation: str, value: float) -> None:
    if DB_QUERY_LATENCY_SECONDS is not None:
        DB_QUERY_LATENCY_SECONDS.labels(operation=str(operation or "unknown")).observe(
            max(0.0, float(value))
        )


def record_auth_fail_open() -> None:
    if AUTH_FAIL_OPEN_TOTAL is not None:
        AUTH_FAIL_OPEN_TOTAL.inc()


def record_auth_fail_closed() -> None:
    if AUTH_FAIL_CLOSED_TOTAL is not None:
        AUTH_FAIL_CLOSED_TOTAL.inc()


def record_backend_timeout(*, operation: str) -> None:
    if BACKEND_TIMEOUT_TOTAL is not None:
        BACKEND_TIMEOUT_TOTAL.labels(operation=str(operation or "unknown")).inc()


def observe_resilience_executor_pressure(*, queue_depth: int) -> None:
    if RESILIENCE_EXECUTOR_QUEUE_DEPTH is not None:
        RESILIENCE_EXECUTOR_QUEUE_DEPTH.set(max(0, int(queue_depth)))
