from __future__ import annotations

import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from keynetra.config.settings import reset_settings_cache
from keynetra.domain.models.idempotency import IdempotencyRecord
from keynetra.domain.models.policy_versioning import PolicyVersion
from keynetra.domain.models.relationship import Relationship
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _build_client(database_url: str) -> TestClient:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"developer","permissions":["policies:write","relationships:write"]}}'
    )
    reset_settings_cache()
    initialize_database(database_url)
    return TestClient(create_app())


def test_policy_create_replays_same_response_without_extra_write(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'core-idempotency.db'}"
    client = _build_client(database_url)
    headers = {"X-API-Key": "testkey", "Idempotency-Key": "policy-1"}
    payload = {"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}}

    first = client.post("/policies", json=payload, headers=headers)
    second = client.post("/policies", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert second.headers["X-Idempotent-Replayed"] == "true"

    session = Session(create_engine(database_url, future=True))
    try:
        assert len(session.execute(select(PolicyVersion)).scalars().all()) == 1
        assert len(session.execute(select(IdempotencyRecord)).scalars().all()) == 1
    finally:
        session.close()


def test_relationship_create_replays_same_response_without_extra_write(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'core-relationships.db'}"
    client = _build_client(database_url)
    headers = {"X-API-Key": "testkey", "Idempotency-Key": "relationship-1"}
    payload = {
        "subject_type": "user",
        "subject_id": "u1",
        "relation": "member",
        "object_type": "team",
        "object_id": "t1",
    }

    first = client.post("/relationships", json=payload, headers=headers)
    second = client.post("/relationships", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert second.headers["X-Idempotent-Replayed"] == "true"

    session = Session(create_engine(database_url, future=True))
    try:
        assert len(session.execute(select(Relationship)).scalars().all()) == 1
    finally:
        session.close()


def test_idempotency_key_rejects_payload_mismatch(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'core-mismatch.db'}"
    client = _build_client(database_url)
    headers = {"X-API-Key": "testkey", "Idempotency-Key": "policy-2"}

    first = client.post(
        "/policies",
        json={"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}},
        headers=headers,
    )
    second = client.post(
        "/policies",
        json={"action": "read", "effect": "deny", "priority": 10, "conditions": {"role": "admin"}},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"
