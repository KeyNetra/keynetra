from __future__ import annotations

import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app

SCHEMA = """
model schema 1
type user
type document
relations
owner: [user]
permissions
read = owner
"""


def test_revision_token_increments_across_model_and_acl_changes(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'revisions.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_POLICIES_JSON"] = "[]"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())
    headers = {"X-API-Key": "testkey"}

    before = client.post(
        "/check-access",
        json={
            "user": {"id": 1, "roles": ["member"]},
            "action": "share_document",
            "resource": {"resource_type": "document", "resource_id": "doc-1"},
            "context": {},
        },
        headers=headers,
    )
    assert before.status_code == 200
    assert before.json()["data"]["revision"] == 1
    assert before.json()["data"]["allowed"] is False

    model_created = client.post("/auth-model", json={"schema": SCHEMA}, headers=headers)
    assert model_created.status_code == 201

    after_model = client.post(
        "/check-access",
        json={
            "user": {"id": 1, "roles": ["member"]},
            "action": "share_document",
            "resource": {"resource_type": "document", "resource_id": "doc-1"},
            "context": {},
        },
        headers=headers,
    )
    assert after_model.status_code == 200
    assert after_model.json()["data"]["revision"] == 2
    assert after_model.json()["data"]["allowed"] is False

    acl_created = client.post(
        "/acl",
        json={
            "subject_type": "user",
            "subject_id": "1",
            "resource_type": "document",
            "resource_id": "doc-1",
            "action": "share_document",
            "effect": "allow",
        },
        headers=headers,
    )
    assert acl_created.status_code == 201

    after_acl = client.post(
        "/check-access",
        json={
            "user": {"id": 1, "roles": ["member"]},
            "action": "share_document",
            "resource": {"resource_type": "document", "resource_id": "doc-1"},
            "context": {},
        },
        headers=headers,
    )
    assert after_acl.status_code == 200
    assert after_acl.json()["data"]["revision"] == 3
