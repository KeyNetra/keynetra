from __future__ import annotations

import os

from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _metric_value(text: str, metric_name: str, labels: dict[str, str] | None = None) -> float:
    labels = labels or {}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.name != metric_name:
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0


def test_metrics_endpoint_exposes_prometheus_text_and_counts_access_checks(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'metrics.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())

    initial_metrics = client.get("/metrics")
    assert initial_metrics.status_code == 200
    assert initial_metrics.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "keynetra_access_checks_total" in initial_metrics.text

    before = _metric_value(
        initial_metrics.text,
        "keynetra_access_checks_total",
        {"tenant": "default", "decision": "allow"},
    )

    check = client.post(
        "/check-access",
        json={
            "user": {"id": 1, "permissions": ["approve_payment"]},
            "action": "approve_payment",
            "resource": {"amount": 5},
            "context": {},
        },
        headers={"X-API-Key": "testkey"},
    )
    assert check.status_code == 200

    updated_metrics = client.get("/metrics")
    after = _metric_value(
        updated_metrics.text,
        "keynetra_access_checks_total",
        {"tenant": "default", "decision": "allow"},
    )

    assert after >= before + 1
