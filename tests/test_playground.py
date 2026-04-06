from __future__ import annotations

import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.main import create_app


def test_playground_evaluate_inline_policy() -> None:
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    reset_settings_cache()
    client = TestClient(create_app())
    payload = {
        "policies": [
            {
                "action": "play",
                "effect": "allow",
                "priority": 10,
                "conditions": {"role": "tester"},
            }
        ],
        "input": {
            "user": {"id": 1, "role": "tester"},
            "resource": {},
            "action": "play",
            "context": {},
        },
    }
    response = client.post("/playground/evaluate", json=payload, headers={"X-API-Key": "testkey"})
    assert response.status_code == 200
    assert response.json()["data"]["decision"] == "allow"
    assert response.json()["data"]["policy_id"] == "play:10:allow"
