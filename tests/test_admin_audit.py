from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt
from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _client(database_url: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def _jwt_headers(*, tenant_key: str, role: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": f"{role}-{tenant_key}",
            "tenant_roles": {tenant_key: role},
        },
        "change-me",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_viewer_can_list_but_cannot_mutate_management_api(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'viewer.db'}")
    admin_headers = {"X-API-Key": "testkey"}
    assert (
        client.post(
            "/policies",
            json={"action": "read", "effect": "allow", "priority": 10, "conditions": {}},
            headers=admin_headers,
        ).status_code
        == 201
    )

    viewer_headers = _jwt_headers(tenant_key="tenant-a", role="viewer")
    listed = client.get("/policies", headers=viewer_headers)
    denied = client.post(
        "/policies",
        json={"action": "write", "effect": "allow", "priority": 20, "conditions": {}},
        headers=viewer_headers,
    )

    assert listed.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "insufficient management role"


def test_developer_role_can_mutate_management_api(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'developer.db'}")
    developer_headers = _jwt_headers(tenant_key="tenant-a", role="developer")

    allowed = client.post(
        "/relationships",
        json={
            "subject_type": "user",
            "subject_id": "u1",
            "relation": "member",
            "object_type": "team",
            "object_id": "t1",
        },
        headers=developer_headers,
    )

    assert allowed.status_code == 201


def test_admin_required_for_global_management_writes(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'admin.db'}")
    developer_headers = _jwt_headers(tenant_key="tenant-a", role="developer")
    admin_headers = _jwt_headers(tenant_key="tenant-a", role="admin")

    denied = client.post("/roles", json={"name": "viewer"}, headers=developer_headers)
    allowed = client.post("/roles", json={"name": "developer"}, headers=admin_headers)

    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == "insufficient management role"
    assert allowed.status_code == 201


def test_audit_endpoints_support_filters_time_range_and_pagination(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'audit.db'}")
    admin_headers = {"X-API-Key": "testkey"}
    viewer_headers = _jwt_headers(tenant_key="tenant-a", role="viewer")

    assert (
        client.post(
            "/policies",
            json={"action": "read", "effect": "allow", "priority": 10, "conditions": {}},
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/check-access",
            json={
                "user": {"id": "u1"},
                "action": "read",
                "resource": {"id": "doc-1"},
                "context": {},
            },
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/check-access",
            json={
                "user": {"id": "u2"},
                "action": "write",
                "resource": {"id": "doc-2"},
                "context": {},
            },
            headers=admin_headers,
        ).status_code
        == 200
    )

    start_time = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    end_time = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    page_one = client.get(
        "/audit",
        params={"limit": 1, "start_time": start_time, "end_time": end_time},
        headers=viewer_headers,
    )
    deny_only = client.get(
        "/audit",
        params={"decision": "deny", "user_id": "u2", "resource_id": "doc-2"},
        headers=viewer_headers,
    )
    page_two = client.get(
        "/audit",
        params={"limit": 1, "cursor": page_one.json()["meta"]["next_cursor"]},
        headers=viewer_headers,
    )

    assert page_one.status_code == 200
    assert len(page_one.json()["data"]) == 1
    assert page_one.json()["meta"]["next_cursor"]
    assert page_two.status_code == 200
    assert len(page_two.json()["data"]) == 1
    assert deny_only.status_code == 200
    assert len(deny_only.json()["data"]) == 1
    assert deny_only.json()["data"][0]["decision"] == "DENY"
    assert deny_only.json()["data"][0]["user"]["id"] == "u2"
