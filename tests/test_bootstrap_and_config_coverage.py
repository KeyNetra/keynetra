from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI

from keynetra.api.main import (
    _bootstrap_file_backed_model,
    _bootstrap_file_backed_policies,
    _start_policy_subscriber,
)
from keynetra.config.config_loader import (
    KeyNetraFileConfig,
    apply_config_to_environment,
    load_config_file,
)
from keynetra.headless import KeyNetra, _parse_descriptor


def test_config_loader_handles_invalid_shapes_and_unsupported_extension(tmp_path: Path) -> None:
    invalid_root = tmp_path / "invalid.json"
    invalid_root.write_text(json.dumps(123), encoding="utf-8")
    with pytest.raises(ValueError, match="configuration root must be an object"):
        load_config_file(invalid_root)

    unsupported = tmp_path / "config.ini"
    unsupported.write_text("x=y", encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported config file format"):
        load_config_file(unsupported)


def test_apply_config_to_environment_sets_all_fields(monkeypatch) -> None:
    cfg = KeyNetraFileConfig(
        database_url="sqlite+pysqlite:///./x.db",
        redis_url="redis://localhost:6379/0",
        policy_paths=("p1", "p2"),
        model_paths=("m1",),
        seed_data=True,
        server_host="127.0.0.1",
        server_port=8089,
    )
    monkeypatch.delenv("KEYNETRA_DATABASE_URL", raising=False)
    apply_config_to_environment(cfg)
    assert os.environ["KEYNETRA_DATABASE_URL"] == "sqlite+pysqlite:///./x.db"
    assert os.environ["KEYNETRA_REDIS_URL"] == "redis://localhost:6379/0"
    assert os.environ["KEYNETRA_POLICY_PATHS"] == "p1,p2"
    assert os.environ["KEYNETRA_MODEL_PATHS"] == "m1"
    assert os.environ["KEYNETRA_AUTO_SEED_SAMPLE_DATA"] == "true"
    assert os.environ["KEYNETRA_SERVER_HOST"] == "127.0.0.1"
    assert os.environ["KEYNETRA_SERVER_PORT"] == "8089"


def test_parse_descriptor_handles_colon_and_non_colon_values() -> None:
    assert _parse_descriptor("user:123") == ("user", "123")
    assert _parse_descriptor("resource") == ("resource", "resource")
    assert _parse_descriptor(":abc") == ("unknown", "abc")


def test_keynetra_load_policies_requires_non_empty(tmp_path: Path) -> None:
    cfg = tmp_path / "keynetra.yaml"
    cfg.write_text("{}", encoding="utf-8")
    app = KeyNetra.from_config(cfg)
    with pytest.raises(ValueError, match="no policies found"):
        app.load_policies(tmp_path / "empty")


def test_keynetra_load_model_and_check_access_string_payloads(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "allow.yaml").write_text(
        "allow:\n  action: read\n  priority: 1\n  when:\n    role: admin\n",
        encoding="utf-8",
    )
    cfg = tmp_path / "keynetra.yaml"
    cfg.write_text(f"policies:\n  path: {policy_dir}\n", encoding="utf-8")
    engine = KeyNetra.from_config(cfg)

    model = tmp_path / "model.yaml"
    model.write_text(
        "model:\n  type: document\n  relations:\n    owner: user\n  permissions:\n    read: owner\n",
        encoding="utf-8",
    )
    engine.load_model(model)
    decision = engine.check_access(
        subject="user:1",
        action="read",
        resource="document:doc-1",
        context={},
    )
    assert decision.decision in {"allow", "deny"}


def test_bootstrap_model_and_policy_helpers_handle_success_and_errors(monkeypatch) -> None:
    class _Settings:
        def parsed_model_paths(self) -> list[str]:
            return ["examples/auth-model.yaml"]

        def load_policies(self) -> list[dict[str, object]]:
            return [{"action": "read", "effect": "allow", "priority": 10, "conditions": {}}]

    monkeypatch.setattr("keynetra.api.main.get_settings", lambda: _Settings())
    _bootstrap_file_backed_model()
    _bootstrap_file_backed_policies()

    class _ErrorSettings(_Settings):
        def load_policies(self) -> list[dict[str, object]]:
            raise RuntimeError("boom")

    monkeypatch.setattr("keynetra.api.main.get_settings", lambda: _ErrorSettings())
    _bootstrap_file_backed_policies()


def test_start_policy_subscriber_handles_none_and_message(monkeypatch) -> None:
    class _Settings:
        policy_events_channel = "policy-events"

    class _FakePubSub:
        def __init__(self) -> None:
            self._subscribed = False

        def subscribe(self, channel: str) -> None:
            self._subscribed = channel == "policy-events"

        def listen(self):
            if not self._subscribed:
                return
            yield {"type": "message", "data": json.dumps({"tenant_key": "acme"})}
            yield {"type": "done"}

    class _FakeRedis:
        def pubsub(self) -> _FakePubSub:
            return _FakePubSub()

    class _Cache:
        def __init__(self) -> None:
            self.invalidated: list[str] = []

        def invalidate(self, tenant_key: str) -> None:
            self.invalidated.append(tenant_key)

    cache = _Cache()
    monkeypatch.setattr("keynetra.api.main.get_settings", lambda: _Settings())
    monkeypatch.setattr("keynetra.api.main.build_policy_cache", lambda _redis: cache)
    monkeypatch.setattr("keynetra.api.main.get_redis", lambda: None)
    _start_policy_subscriber(FastAPI())

    monkeypatch.setattr("keynetra.api.main.get_redis", lambda: _FakeRedis())
    app = FastAPI()
    _start_policy_subscriber(app)
    assert hasattr(app.state, "policy_subscriber")
    app.state.policy_subscriber.join(timeout=1)
    assert "acme" in cache.invalidated
