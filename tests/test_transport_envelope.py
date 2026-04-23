from __future__ import annotations

import os
from typing import Any

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from jose import jwt

from keynetra.api.errors import ApiErrorCode
from keynetra.api.responses import error_response
from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _client(database_url: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
    )
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def _path_value(name: str) -> str:
    if name in {
        "version",
        "from_version",
        "to_version",
        "role_id",
        "permission_id",
        "acl_id",
        "key_id",
    }:
        return "1"
    if name == "tenant_key":
        return "acme"
    if name == "external_id":
        return "u-1"
    if name == "policy_key":
        return "policy-1"
    if name == "resource":
        return "roles"
    if name == "resource_type":
        return "document"
    if name == "resource_id":
        return "doc-1"
    return "value"


def _materialize_path(path: str) -> str:
    rendered = path
    while "{" in rendered and "}" in rendered:
        start = rendered.index("{")
        end = rendered.index("}", start)
        name = rendered[start + 1 : end]
        rendered = rendered[:start] + _path_value(name) + rendered[end + 1 :]
    return rendered


def _json_payload_for(method: str) -> dict[str, Any] | None:
    if method in {"POST", "PUT", "PATCH"}:
        return {}
    return None


def test_all_documented_routes_use_success_response_model() -> None:
    app = create_app()

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        assert "SuccessResponse" in str(route.response_model), route.path


def test_middleware_order_prioritizes_request_context_before_validation() -> None:
    app = create_app()

    assert [middleware.cls.__name__ for middleware in app.user_middleware[:3]] == [
        "RequestIdMiddleware",
        "ApiVersionMiddleware",
        "TenantResolverMiddleware",
    ]


def test_all_documented_json_routes_return_standard_envelope(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'transport.db'}")
    app = create_app()

    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        method = next(
            iter(sorted(m for m in (route.methods or set()) if m not in {"HEAD", "OPTIONS"})), None
        )
        if method is None:
            continue
        if route.path == "/metrics":
            # Prometheus uses text/plain exposition format and is intentionally not envelope-wrapped.
            continue
        path = _materialize_path(route.path)
        response = client.request(method, path, json=_json_payload_for(method))
        assert response.headers.get("X-Request-Id"), f"{method} {path}"
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            continue
        body = response.json()
        assert set(body) == {"data", "meta", "error"}, f"{method} {path}"
        assert set(body["meta"]) == {
            "request_id",
            "limit",
            "next_cursor",
            "extra",
        }, f"{method} {path}"
        assert body["meta"]["request_id"], f"{method} {path}"


def test_invalid_tenant_header_returns_standard_error_envelope(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'tenant.db'}")

    response = client.get("/roles", headers={"X-API-Key": "testkey", "X-Tenant-Id": "!bad"})

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "invalid tenant header"
    assert response.json()["meta"]["request_id"]


def test_metrics_remains_text_plain_and_not_enveloped(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'metrics.db'}")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers.get("X-Request-Id")
    assert response.headers["content-type"].startswith("text/plain")
    assert not response.text.lstrip().startswith("{")


def test_error_codes_are_from_strict_enum(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'errors.db'}")
    allowed_codes = {str(code) for code in ApiErrorCode}

    responses = [
        client.get("/health", headers={"X-API-Version": "v2"}),
        client.get("/roles", headers={"X-API-Key": "testkey", "X-Tenant-Id": "!bad"}),
        client.post("/check-access", json={"user": {}, "action": "x", "resource": {}}),
    ]

    for response in responses:
        payload = response.json()
        assert payload["error"]["code"] in allowed_codes

    try:
        error_response(code="not_a_real_code", message="boom")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown error code was accepted")


def test_datetime_values_are_utc_z_strings_in_api_responses(tmp_path) -> None:
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'datetimes.db'}")
    headers = {"X-API-Key": "testkey"}

    tenant = client.post("/tenants", json={"tenant_key": "acme"}, headers=headers)
    assert tenant.status_code == 201

    created = client.post(
        "/tenants/acme/api-keys",
        json={"name": "automation", "scopes": {"permissions": ["*"]}},
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["data"]["created_at"].endswith("Z")

    listed = client.get("/tenants/acme/api-keys", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"][0]["created_at"].endswith("Z")


def test_strict_tenant_missing_header_returns_standard_error_envelope(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("KEYNETRA_STRICT_TENANCY", "true")
    client = _client(f"sqlite+pysqlite:///{tmp_path / 'strict-tenant.db'}")

    token = jwt.encode({"sub": "viewer", "role": "viewer"}, "change-me", algorithm="HS256")
    response = client.get("/roles", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422
    assert response.json()["error"]["message"] == "tenant is required"
    assert response.json()["meta"]["request_id"]
