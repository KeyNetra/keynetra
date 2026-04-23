from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.main import create_app

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "openapi.yaml"
CONTRACT_JSON_PATH = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"


def _normalize_request_id(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    meta = dict(normalized.get("meta") or {})
    if meta.get("request_id") is not None:
        meta["request_id"] = "<request-id>"
    normalized["meta"] = meta
    return normalized


def test_openapi_contract_includes_stable_paths_and_schemas() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "openapi: 3.0.3" in contract
    assert "/health:" in contract
    assert "/check-access:" in contract
    assert "/simulate:" in contract
    assert "/check-access-batch:" in contract
    assert "/simulate-policy:" in contract
    assert "/impact-analysis:" in contract
    assert "/metrics:" in contract
    assert "SuccessResponse_dict_str__str__" in contract
    assert "SuccessResponse_AccessDecisionResponse_" in contract
    assert "APIKeyHeader" in contract
    assert "HTTPBearer" in contract
    assert "X-Tenant-Id" in contract
    assert "X-API-Version" in contract
    assert "ErrorResponse" in contract


def test_openapi_schema_is_sdk_friendly() -> None:
    schema = create_app().openapi()
    policies_dsl = schema["paths"]["/policies/dsl"]["post"]
    check_access = schema["paths"]["/check-access"]["post"]
    admin_login = schema["paths"]["/admin/login"]["post"]
    roles_create = schema["paths"]["/roles"]["post"]

    assert schema["openapi"] == "3.0.3"
    assert schema["servers"] == [
        {
            "url": "/",
            "description": "Relative base URL. Configure the SDK/client host per environment.",
        }
    ]
    assert "requestBody" in policies_dsl
    assert '"type": "null"' not in json.dumps(schema)
    assert check_access["operationId"] == "check_access"
    assert policies_dsl["operationId"] == "create_policy_from_dsl"
    assert admin_login["tags"] == ["auth"]
    assert "/dev/sample-data" not in schema["paths"]
    assert "/dev/sample-data/seed" not in schema["paths"]
    assert any(
        parameter.get("$ref") == "#/components/parameters/ApiVersionHeader"
        for parameter in policies_dsl["parameters"]
        if isinstance(parameter, dict)
    )
    assert any(
        parameter.get("$ref") == "#/components/parameters/TenantHeader"
        for parameter in check_access["parameters"]
        if isinstance(parameter, dict)
    )
    assert (
        roles_create["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/SuccessResponse_RoleOut_"
    )
    assert (
        schema["components"]["schemas"]["ErrorResponse"]["properties"]["meta"]["$ref"]
        == "#/components/schemas/MetaBody"
    )
    assert (
        schema["components"]["schemas"]["ErrorBody"]["properties"]["code"]["$ref"]
        == "#/components/schemas/ApiErrorCode"
    )


def test_generated_openapi_matches_checked_in_contract_files() -> None:
    schema = create_app().openapi()
    assert schema == json.loads(CONTRACT_JSON_PATH.read_text(encoding="utf-8"))


def test_openapi_paths_include_required_headers_and_component_refs() -> None:
    schema = create_app().openapi()

    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            parameters = operation.get("parameters", [])
            assert any(
                parameter.get("$ref") == "#/components/parameters/ApiVersionHeader"
                for parameter in parameters
                if isinstance(parameter, dict)
            ), f"{method.upper()} {path} missing X-API-Version header"

            requires_tenant = path.startswith(
                (
                    "/check-access",
                    "/simulate",
                    "/policies",
                    "/roles",
                    "/permissions",
                    "/relationships",
                    "/playground",
                    "/audit",
                    "/tenants",
                    "/users",
                    "/policy-tests",
                    "/bulk",
                )
            )
            if requires_tenant:
                assert any(
                    parameter.get("$ref") == "#/components/parameters/TenantHeader"
                    for parameter in parameters
                    if isinstance(parameter, dict)
                ), f"{method.upper()} {path} missing X-Tenant-Id header"

            for status_code, response in operation["responses"].items():
                if "$ref" in response:
                    continue
                headers = response.get("headers", {})
                assert (
                    headers.get("X-Request-Id", {}).get("$ref")
                    == "#/components/headers/RequestIdHeader"
                )
                assert (
                    headers.get("X-API-Version", {}).get("$ref")
                    == "#/components/headers/ApiVersionHeader"
                )
                if path == "/metrics":
                    text_plain = response.get("content", {}).get("text/plain")
                    assert text_plain is not None
                    assert text_plain["schema"]["type"] == "string"
                    continue
                app_json = response.get("content", {}).get("application/json")
                if app_json is None:
                    continue
                schema_ref = app_json.get("schema", {})
                assert (
                    "$ref" in schema_ref
                ), f"{method.upper()} {path} {status_code} uses an inline JSON schema"
                assert app_json.get(
                    "examples"
                ), f"{method.upper()} {path} {status_code} missing OpenAPI examples"


def test_health_response_matches_snapshot() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert _normalize_request_id(response.json()) == {
        "data": {"status": "ok"},
        "meta": {"request_id": "<request-id>", "limit": None, "next_cursor": None, "extra": {}},
        "error": None,
    }


def test_check_access_response_matches_snapshot() -> None:
    import os

    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    reset_settings_cache()
    client = TestClient(create_app())

    response = client.post(
        "/check-access",
        json={
            "user": {"id": 1, "role": "employee", "permissions": ["approve_payment"]},
            "action": "approve_payment",
            "resource": {"amount": 5},
            "context": {},
        },
        headers={"X-API-Key": "testkey"},
    )

    assert response.status_code == 200
    body = _normalize_request_id(response.json())
    assert body == {
        "data": {
            "allowed": True,
            "decision": "allow",
            "matched_policies": ["rbac:permissions"],
            "reason": "explicit permission grant",
            "policy_id": "rbac:permissions",
            "revision": 1,
            "explain_trace": [
                {
                    "step": "start",
                    "outcome": "continue",
                    "detail": "evaluate action=approve_payment",
                    "policy_id": None,
                },
                {
                    "step": "rbac_permissions",
                    "outcome": "matched",
                    "detail": "explicit permission grant matched input action",
                    "policy_id": "rbac:permissions",
                },
                {
                    "step": "final",
                    "outcome": "allow",
                    "detail": "granted by explicit permission",
                    "policy_id": "rbac:permissions",
                },
            ],
        },
        "meta": {"request_id": "<request-id>", "limit": None, "next_cursor": None, "extra": {}},
        "error": None,
    }


def test_error_response_matches_snapshot() -> None:
    client = TestClient(create_app())

    response = client.get("/health", headers={"X-API-Version": "v2"})

    assert response.status_code == 400
    assert _normalize_request_id(response.json()) == {
        "data": None,
        "meta": {"request_id": "<request-id>", "limit": None, "next_cursor": None, "extra": {}},
        "error": {
            "code": "bad_request",
            "message": "unsupported api version",
            "details": {
                "requested_version": "v2",
                "supported_versions": ["v1"],
            },
        },
    }
