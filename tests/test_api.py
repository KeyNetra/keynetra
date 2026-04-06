from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _normalize_response(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    meta = dict(normalized.get("meta") or {})
    if "request_id" in meta and meta["request_id"] is not None:
        meta["request_id"] = "<request-id>"
    normalized["meta"] = meta
    return normalized


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    assert _normalize_response(resp.json()) == {
        "data": {"status": "ok"},
        "meta": {"request_id": "<request-id>", "limit": None, "next_cursor": None, "extra": {}},
        "error": None,
    }


def test_health_live_and_ready_ok(tmp_path) -> None:
    import os

    database_url = f"sqlite+pysqlite:///{tmp_path / 'health-ready.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())

    live = client.get("/health/live")
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["data"]["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["data"]["checks"]["database"]["status"] == "ok"
    assert ready.json()["data"]["checks"]["redis"]["status"] == "not_configured"


def test_check_access_rbac_permissions_allow() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1, "role": "employee", "permissions": ["approve_payment"]},
        "action": "approve_payment",
        "resource": {"amount": 999999},
    }
    resp = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["allowed"] is True
    assert data["decision"] == "allow"
    assert data["policy_id"] == "rbac:permissions"
    assert data["revision"] == 1
    assert isinstance(data["explain_trace"], list)
    assert resp.json()["error"] is None


def test_check_access_abac_policy_allow() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1, "role": "manager", "permissions": []},
        "action": "approve_payment",
        "resource": {"amount": 50000, "owner_id": 2},
    }
    resp = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["allowed"] is True
    assert data["decision"] == "allow"
    assert data["policy_id"]
    assert data["revision"] == 1


def test_check_access_default_deny() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {"user": {"id": 1, "role": "employee"}, "action": "unknown", "resource": {}}
    resp = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["allowed"] is False
    assert data["decision"] == "deny"
    assert data["reason"]
    assert isinstance(data["explain_trace"], list)


def test_check_access_requires_auth() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    reset_settings_cache()
    client = TestClient(create_app())
    resp = client.post("/check-access", json={"user": {}, "action": "x", "resource": {}})
    assert resp.status_code == 401
    assert resp.json()["data"] is None
    assert resp.json()["error"]["code"] == "unauthorized"


def test_check_access_rate_limited() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_WINDOW_SECONDS"] = "60"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1},
        "action": "approve_payment",
        "resource": {"amount": 1},
        "context": {},
    }

    first = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})
    second = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["data"] is None
    assert second.json()["error"]["code"] == "too_many_requests"


def test_check_access_burst_is_throttled() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "2"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "2"
    os.environ["KEYNETRA_RATE_LIMIT_WINDOW_SECONDS"] = "60"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1},
        "action": "approve_payment",
        "resource": {"amount": 1},
        "context": {},
    }
    headers = {"X-API-Key": "testkey"}

    first = client.post("/check-access", json=payload, headers=headers)
    second = client.post("/check-access", json=payload, headers=headers)
    third = client.post("/check-access", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "too_many_requests"


def test_check_access_rate_limit_is_global() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_WINDOW_SECONDS"] = "60"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1},
        "action": "approve_payment",
        "resource": {"amount": 1},
        "context": {},
    }

    tenant_a = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})
    tenant_b = client.post("/check-access", json=payload, headers={"X-API-Key": "testkey"})

    assert tenant_a.status_code == 200
    assert tenant_b.status_code == 429


def test_check_access_rate_limit_uses_redis_backend(monkeypatch) -> None:
    import os

    class FakeRedis:
        def __init__(self) -> None:
            self.calls = 0

        def eval(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return [1, 0, 0]
            return [0, 0, 60]

    fake = FakeRedis()
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_WINDOW_SECONDS"] = "60"
    reset_settings_cache()
    monkeypatch.setattr("keynetra.config.rate_limit.get_redis", lambda: fake)
    client = TestClient(create_app())
    payload = {
        "user": {"id": 1},
        "action": "approve_payment",
        "resource": {"amount": 1},
        "context": {},
    }
    headers = {"X-API-Key": "testkey"}

    first = client.post("/check-access", json=payload, headers=headers)
    second = client.post("/check-access", json=payload, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert fake.calls == 2


def test_health_is_not_rate_limited() -> None:
    import os

    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1"
    os.environ["KEYNETRA_RATE_LIMIT_WINDOW_SECONDS"] = "60"
    reset_settings_cache()
    client = TestClient(create_app())

    first = client.get("/health")
    second = client.get("/health")

    assert first.status_code == 200
    assert second.status_code == 200
