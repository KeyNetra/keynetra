from __future__ import annotations

import os

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from keynetra.config.settings import reset_settings_cache
from keynetra.domain.models.tenant import Tenant
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _strict_client(database_url: str, *, scopes_json: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = scopes_json
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_STRICT_TENANCY"] = "true"
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def _create_tenant(database_url: str, tenant_key: str) -> None:
    session = Session(create_engine(database_url, future=True))
    try:
        SqlTenantRepository(session).create(tenant_key)
    finally:
        session.close()


def test_check_access_requires_explicit_tenant_when_strict(tmp_path) -> None:
    client = _strict_client(
        f"sqlite+pysqlite:///{tmp_path / 'strict-access.db'}",
        scopes_json='{"testkey":{"role":"admin","permissions":["*"]}}',
    )
    headers = {"X-API-Key": "testkey"}

    missing_tenant = client.post(
        "/check-access",
        json={
            "user": {"id": "u1"},
            "action": "read",
            "resource": {"id": "doc-1"},
            "context": {},
        },
        headers=headers,
    )
    assert missing_tenant.status_code == 422
    assert missing_tenant.json()["error"]["message"] == "tenant is required"

    explicit_tenant = client.post(
        "/check-access",
        json={
            "user": {"id": "u1"},
            "action": "read",
            "resource": {"id": "doc-1"},
            "context": {},
        },
        headers={**headers, "X-Tenant-Id": "acme"},
    )
    assert explicit_tenant.status_code == 404
    assert explicit_tenant.json()["error"]["message"] == "tenant not found"

    _create_tenant(
        f"sqlite+pysqlite:///{tmp_path / 'strict-access.db'}",
        "acme",
    )
    known_tenant = client.post(
        "/check-access",
        json={
            "user": {"id": "u1"},
            "action": "read",
            "resource": {"id": "doc-1"},
            "context": {},
        },
        headers={**headers, "X-Tenant-Id": "acme"},
    )
    assert known_tenant.status_code == 200


def test_management_routes_require_tenant_when_strict(tmp_path) -> None:
    client = _strict_client(
        f"sqlite+pysqlite:///{tmp_path / 'strict-management.db'}",
        scopes_json='{"testkey":{"role":"admin","permissions":["*"]}}',
    )
    token = jwt.encode({"sub": "viewer", "role": "viewer"}, "change-me", algorithm="HS256")
    jwt_headers = {"Authorization": f"Bearer {token}"}

    missing_tenant = client.get("/roles", headers=jwt_headers)
    assert missing_tenant.status_code == 422
    assert missing_tenant.json()["error"]["message"] == "tenant is required"

    explicit_tenant = client.get("/roles", headers={**jwt_headers, "X-Tenant-Id": "acme"})
    assert explicit_tenant.status_code == 404
    assert explicit_tenant.json()["error"]["message"] == "tenant not found"

    _create_tenant(
        f"sqlite+pysqlite:///{tmp_path / 'strict-management.db'}",
        "acme",
    )
    known_tenant = client.get("/roles", headers={**jwt_headers, "X-Tenant-Id": "acme"})
    assert known_tenant.status_code == 200


def test_unknown_tenant_header_does_not_create_tenant(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'strict-no-create.db'}"
    client = _strict_client(
        database_url,
        scopes_json='{"testkey":{"role":"admin","permissions":["*"]}}',
    )
    response = client.post(
        "/check-access",
        json={
            "user": {"id": "u1"},
            "action": "read",
            "resource": {"id": "doc-1"},
            "context": {},
        },
        headers={"X-API-Key": "testkey", "X-Tenant-Id": "unknown"},
    )

    assert response.status_code == 404

    session = Session(create_engine(database_url, future=True))
    try:
        tenant_keys = [row.tenant_key for row in session.execute(select(Tenant)).scalars().all()]
    finally:
        session.close()
    assert tenant_keys == []
