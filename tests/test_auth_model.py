from __future__ import annotations

import os

from fastapi.testclient import TestClient

from keynetra.config.settings import reset_settings_cache
from keynetra.engine.keynetra_engine import AuthorizationInput
from keynetra.infrastructure.storage.session import initialize_database
from keynetra.main import create_app
from keynetra.modeling import (
    compile_authorization_schema,
    parse_authorization_schema,
    validate_authorization_schema,
)

SCHEMA = """
model schema 1
type user
type document
relations
owner: [user]
viewer: [user]
permissions
read = viewer or owner
"""


def test_authorization_schema_parsing_and_compilation() -> None:
    schema = parse_authorization_schema(SCHEMA)
    validate_authorization_schema(schema)
    graph = compile_authorization_schema(schema)

    decision = graph.permissions["read"].name
    assert decision == "read"

    runtime = graph.to_dict()
    assert runtime["version"] == 1
    assert runtime["permissions"]["read"]["kind"] == "or"

    from keynetra.engine.model_graph.permission_graph import CompiledPermissionGraph

    compiled = CompiledPermissionGraph(tenant_key="default", model=graph)
    allowed = compiled.evaluate(
        AuthorizationInput(
            user={
                "id": 1,
                "relations": [
                    {"relation": "viewer", "object_type": "document", "object_id": "doc-1"}
                ],
            },
            action="read",
            resource={"resource_type": "document", "resource_id": "doc-1"},
        )
    )
    assert allowed.outcome == "allow"


def test_auth_model_route_round_trip(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'auth-model.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_API_KEYS"] = "testkey"
    os.environ["KEYNETRA_RATE_LIMIT_PER_MINUTE"] = "1000"
    os.environ["KEYNETRA_RATE_LIMIT_BURST"] = "1000"
    reset_settings_cache()
    initialize_database(database_url)
    client = TestClient(create_app())

    created = client.post("/auth-model", json={"schema": SCHEMA}, headers={"X-API-Key": "testkey"})
    assert created.status_code == 201
    assert created.json()["data"]["schema"].strip().startswith("model schema 1")

    fetched = client.get("/auth-model", headers={"X-API-Key": "testkey"})
    assert fetched.status_code == 200
    assert fetched.json()["data"]["compiled"]["version"] == 1
