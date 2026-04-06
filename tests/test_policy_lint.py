from __future__ import annotations

import os

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from keynetra.config.settings import reset_settings_cache
from keynetra.domain.models.base import Base
from keynetra.domain.models.rbac import Role
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app


def _setup_database(database_url: str) -> None:
    initialize_database(database_url)
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Role(name="orphan"))
        session.commit()


def test_policy_creation_emits_role_warning(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'lint.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    _setup_database(database_url)
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_API_KEY_SCOPES_JSON"] = (
        '{"testkey":{"tenant":"default","role":"developer","permissions":["policies:write"]}}'
    )
    reset_settings_cache()
    client = TestClient(create_app())
    headers = {"X-API-Key": "testkey"}

    policy = {
        "action": "read",
        "effect": "allow",
        "priority": 10,
        "conditions": {},
    }

    response = client.post("/policies", json=policy, headers=headers)
    assert response.status_code == 201
    warnings = response.json()["meta"]["extra"].get("warnings")
    assert warnings
    assert any("orphan" in warning for warning in warnings)
