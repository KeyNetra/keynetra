from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.main import create_app

CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "contracts" / "openapi" / "keynetra-v0.1.0.yaml"
)


def _normalize_request_id(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    meta = dict(normalized.get("meta") or {})
    if meta.get("request_id") is not None:
        meta["request_id"] = "<request-id>"
    normalized["meta"] = meta
    return normalized


def test_openapi_contract_includes_stable_paths_and_schemas() -> None:
    contract = CONTRACT_PATH.read_text(encoding="utf-8")

    assert "openapi: 3.1.0" in contract
    assert "/health:" in contract
    assert "/check-access:" in contract
    assert "/simulate:" in contract
    assert "/check-access-batch:" in contract
    assert "/simulate-policy:" in contract
    assert "/impact-analysis:" in contract
    assert "SuccessResponse_dict_str__str__" in contract
    assert "SuccessResponse_AccessDecisionResponse_" in contract
    assert "APIKeyHeader" in contract
    assert "HTTPBearer" in contract


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
