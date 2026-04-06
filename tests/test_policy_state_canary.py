from __future__ import annotations

import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def test_draft_policy_set_isolated_from_active(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path}/policy-state.db"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"developer","permissions":["policies:write"]}}'
    )
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())
    headers = {"X-API-Key": "testkey"}

    active = client.post(
        "/policies",
        headers=headers,
        json={
            "action": "download_report",
            "effect": "deny",
            "priority": 1,
            "state": "active",
            "conditions": {"policy_key": "download_report"},
        },
    )
    assert active.status_code == 201

    draft = client.put(
        "/policies/download_report",
        headers=headers,
        json={
            "action": "download_report",
            "effect": "allow",
            "priority": 1,
            "state": "draft",
            "conditions": {"policy_key": "download_report"},
        },
    )
    assert draft.status_code == 200

    payload = {"user": {"id": 1}, "action": "download_report", "resource": {"id": "r1"}}
    active_eval = client.post("/check-access", headers=headers, json=payload)
    draft_eval = client.post("/check-access?policy_set=draft", headers=headers, json=payload)
    assert active_eval.status_code == 200
    assert draft_eval.status_code == 200
    assert active_eval.json()["data"]["allowed"] is False
    assert draft_eval.json()["data"]["allowed"] is True
