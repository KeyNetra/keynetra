from __future__ import annotations

import hashlib
import logging
import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _client(database_url: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def test_roles_cursor_pagination_and_version_header(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'roles.db'}"
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    client = _client(database_url)

    first = client.post("/roles", json={"name": "admin"}, headers={"X-API-Key": "testkey"})
    second = client.post("/roles", json={"name": "member"}, headers={"X-API-Key": "testkey"})

    assert first.status_code == 201
    assert second.status_code == 201

    page_one = client.get("/roles?limit=1", headers={"X-API-Key": "testkey"})
    assert page_one.status_code == 200
    assert page_one.headers["X-API-Version"] == "v1"
    assert len(page_one.json()["data"]) == 1
    assert page_one.json()["meta"]["next_cursor"]

    page_two = client.get(
        f"/roles?limit=1&cursor={page_one.json()['meta']['next_cursor']}",
        headers={"X-API-Key": "testkey", "X-API-Version": "v1"},
    )
    assert page_two.status_code == 200
    assert page_two.json()["data"][0]["name"] == "member"


def test_policies_cursor_pagination(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'policies.db'}"
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    client = _client(database_url)
    headers = {"X-API-Key": "testkey"}

    assert (
        client.post(
            "/policies",
            json={"action": "read", "effect": "allow", "priority": 10, "conditions": {}},
            headers=headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/policies",
            json={"action": "write", "effect": "allow", "priority": 20, "conditions": {}},
            headers=headers,
        ).status_code
        == 201
    )

    response = client.get("/policies?limit=1", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["meta"]["limit"] == 1
    assert response.json()["meta"]["next_cursor"]


def test_hashed_api_key_auth_and_failed_attempt_logging(tmp_path, caplog) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'auth.db'}"
    os.environ.pop("KEYNETRA_API_KEYS", None)
    os.environ["KEYNETRA_API_KEY_HASHES"] = hashlib.sha256(b"testkey").hexdigest()
    client = _client(database_url)

    ok = client.get("/health", headers={"X-API-Key": "testkey"})
    assert ok.status_code == 200

    caplog.set_level(logging.INFO)
    bad = client.post(
        "/check-access",
        json={"user": {}, "action": "read", "resource": {}},
        headers={"X-API-Key": "badkey"},
    )
    assert bad.status_code == 401
    assert any("auth_failed" in str(record.msg) for record in caplog.records)


def test_unsupported_api_version_rejected(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'version.db'}"
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    client = _client(database_url)

    response = client.get("/health", headers={"X-API-Version": "v2"})

    assert response.status_code == 400
    assert response.json()["meta"]["request_id"]
    assert response.json()["error"]["message"] == "unsupported api version"
