from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'enterprise.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def test_enterprise_management_surface(tmp_path: Path) -> None:
    client = _client(tmp_path)
    default_headers = {"X-API-Key": "testkey"}

    created_tenant = client.post("/tenants", json={"tenant_key": "acme"}, headers=default_headers)
    assert created_tenant.status_code == 201
    assert created_tenant.json()["data"]["tenant_key"] == "acme"

    created_key = client.post(
        "/tenants/acme/api-keys",
        json={"name": "automation", "scopes": {"permissions": ["*"]}},
        headers=default_headers,
    )
    assert created_key.status_code == 201
    secret = created_key.json()["data"]["secret"]
    acme_headers = {"X-API-Key": secret}

    tenant_detail = client.get("/tenants/acme", headers=acme_headers)
    assert tenant_detail.status_code == 200
    assert tenant_detail.json()["data"]["tenant_key"] == "acme"

    api_keys = client.get("/tenants/acme/api-keys", headers=acme_headers)
    assert api_keys.status_code == 200
    assert api_keys.json()["data"][0]["name"] == "automation"

    role = client.post("/roles", json={"name": "operators"}, headers=acme_headers)
    assert role.status_code == 201
    role_id = role.json()["data"]["id"]

    assigned_role = client.post(f"/users/u-1/roles/{role_id}", headers=acme_headers)
    assert assigned_role.status_code == 200
    assert "operators" in assigned_role.json()["data"]["roles"]

    user_roles = client.get("/users/u-1/roles", headers=acme_headers)
    assert user_roles.status_code == 200
    assert "operators" in user_roles.json()["data"][0]["roles"]

    created_policy = client.post(
        "/policies",
        json={
            "action": "read_document",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin", "policy_key": "read-document"},
        },
        headers=acme_headers,
    )
    assert created_policy.status_code == 201

    updated_policy = client.put(
        "/policies/read-document",
        json={
            "action": "read_document",
            "effect": "deny",
            "priority": 5,
            "conditions": {"role": "operator"},
        },
        headers=acme_headers,
    )
    assert updated_policy.status_code == 200

    versions = client.get("/policies/read-document/versions", headers=acme_headers)
    assert versions.status_code == 200
    assert len(versions.json()["data"]) == 2

    diff = client.get(
        "/policies/read-document/versions/1/diff/2",
        headers=acme_headers,
    )
    assert diff.status_code == 200
    assert diff.json()["data"]["changes"]

    restore = client.post(
        "/policies/read-document/versions/1/restore",
        headers=acme_headers,
    )
    assert restore.status_code == 200
    assert restore.json()["data"]["current_version"] >= 1

    policy_tests = client.post(
        "/policy-tests/run",
        json={
            "document": json.dumps(
                {
                    "policies": [
                        {
                            "action": "read",
                            "effect": "allow",
                            "priority": 1,
                            "conditions": {"role": "admin"},
                        }
                    ],
                    "tests": [
                        {
                            "name": "admin read",
                            "expect": "allow",
                            "input": {
                                "user": {"id": "u-1", "role": "admin"},
                                "action": "read",
                                "resource": {"resource_type": "document", "resource_id": "doc-1"},
                                "context": {},
                            },
                        }
                    ],
                }
            )
        },
        headers=acme_headers,
    )
    assert policy_tests.status_code == 200
    assert policy_tests.json()["data"][0]["passed"] is True

    export_roles = client.get("/bulk/export/roles", headers=acme_headers)
    assert export_roles.status_code == 200
    assert any(item["name"] == "operators" for item in export_roles.json()["data"]["data"])

    import_permissions = client.post(
        "/bulk/import",
        json={"resource": "permissions", "payload": [{"action": "export_audit"}]},
        headers=acme_headers,
    )
    assert import_permissions.status_code == 200
    assert import_permissions.json()["data"]["imported"] == 1

    decision = client.post(
        "/check-access",
        json={
            "user": {"id": "u-1", "role": "admin"},
            "action": "read_document",
            "resource": {"resource_type": "document", "resource_id": "doc-1"},
            "context": {},
        },
        headers=acme_headers,
    )
    assert decision.status_code == 200

    audit_export = client.get("/audit/export?limit=20&user_id=u-1", headers=acme_headers)
    assert audit_export.status_code == 200
    assert len(audit_export.json()["data"]) >= 1
