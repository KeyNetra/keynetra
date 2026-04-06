from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from keynetra import KeyNetra
from keynetra.cli import app
from keynetra.config.config_loader import load_config_file
from keynetra.config.file_loaders import (
    load_authorization_model_from_file,
    load_policies_from_file,
    load_policies_from_paths,
)
from keynetra.engine import KeyNetraEngine


def test_config_loader_supports_yaml_json_and_toml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "keynetra.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "database:",
                "  url: sqlite+pysqlite:///./headless.db",
                "redis:",
                "  url: redis://localhost:6379/0",
                "policies:",
                "  path: ./policies",
                "models:",
                "  path: ./auth-model.yaml",
                "server:",
                "  host: 127.0.0.1",
                "  port: 8088",
            ]
        ),
        encoding="utf-8",
    )
    json_path = tmp_path / "keynetra.json"
    json_path.write_text(
        json.dumps(
            {
                "database": {"url": "sqlite+pysqlite:///./headless.db"},
                "policies": {"path": "./policies"},
            }
        ),
        encoding="utf-8",
    )
    toml_path = tmp_path / "keynetra.toml"
    toml_path.write_text(
        "\n".join(
            [
                "[database]",
                "url = 'sqlite+pysqlite:///./headless.db'",
                "[server]",
                "host = '127.0.0.1'",
                "port = 9000",
            ]
        ),
        encoding="utf-8",
    )

    cfg_yaml = load_config_file(yaml_path)
    cfg_json = load_config_file(json_path)
    cfg_toml = load_config_file(toml_path)

    assert cfg_yaml.database_url == "sqlite+pysqlite:///./headless.db"
    assert cfg_yaml.policy_paths == ("./policies",)
    assert cfg_json.database_url == "sqlite+pysqlite:///./headless.db"
    assert cfg_toml.server_port == 9000


def test_policy_file_loader_supports_yaml_json_and_polar(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "a.yaml").write_text(
        "allow:\n  action: read\n  priority: 10\n  when:\n    role: admin\n", encoding="utf-8"
    )
    (policy_dir / "b.json").write_text(
        json.dumps(
            [
                {
                    "action": "write",
                    "effect": "allow",
                    "priority": 20,
                    "conditions": {"owner_only": True},
                }
            ]
        ),
        encoding="utf-8",
    )
    (policy_dir / "c.polar").write_text(
        "allow action=deploy priority=5 role=ops\n",
        encoding="utf-8",
    )

    policies = load_policies_from_paths([str(policy_dir)])

    assert len(policies) == 3
    assert any(policy["action"] == "deploy" for policy in policies)


def test_engine_check_access_headless_api() -> None:
    engine = KeyNetraEngine(
        [{"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}}]
    )
    decision = engine.check_access(
        subject={"id": "123", "role": "admin"},
        action="read",
        resource="document:abc",
        context={},
    )
    assert decision.allowed is True


def test_embedded_keynetra_from_config_and_model_loading(tmp_path: Path) -> None:
    policy_dir = tmp_path / "policies"
    policy_dir.mkdir()
    (policy_dir / "document.yaml").write_text(
        json.dumps([{"action": "read", "effect": "deny", "priority": 100, "conditions": {}}]),
        encoding="utf-8",
    )
    model_path = tmp_path / "auth-model.yaml"
    model_path.write_text(
        "\n".join(
            [
                "model:",
                "  type: document",
                "  relations:",
                "    owner: user",
                "  permissions:",
                "    read: owner",
            ]
        ),
        encoding="utf-8",
    )
    cfg_path = tmp_path / "keynetra.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "policies:",
                f"  path: {policy_dir}",
                "models:",
                f"  path: {model_path}",
            ]
        ),
        encoding="utf-8",
    )

    engine = KeyNetra.from_config(cfg_path)
    decision = engine.check_access(
        subject={
            "id": "1",
            "relations": [{"relation": "owner", "object_type": "document", "object_id": "abc"}],
        },
        action="read",
        resource="document:abc",
        context={},
    )
    assert decision.allowed is True


def test_cli_serve_with_config_uses_server_settings(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(app_path: str, host: str, port: int, reload: bool) -> None:
        captured["app_path"] = app_path
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setattr("uvicorn.run", fake_run)

    cfg_path = tmp_path / "keynetra.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "server:",
                "  host: 127.0.0.1",
                "  port: 9099",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--config", str(cfg_path)])

    assert result.exit_code == 0
    assert captured["app_path"] == "keynetra.api.main:app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9099


def test_cli_check_with_config_builds_url_from_server_settings(tmp_path: Path, monkeypatch) -> None:
    called: dict[str, object] = {}

    class _Response:
        text = '{"ok": true}'

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, json: dict[str, object], headers: dict[str, str], timeout: float):
        called["url"] = url
        called["json"] = json
        called["headers"] = headers
        called["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("httpx.post", fake_post)
    cfg_path = tmp_path / "keynetra.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "server:",
                "  host: 127.0.0.1",
                "  port: 8087",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "check",
            "--config",
            str(cfg_path),
            "--api-key",
            "devkey",
            "--action",
            "read",
            "--user",
            '{"id":"1"}',
            "--resource",
            '{"resource_type":"document","resource_id":"doc-1"}',
        ],
    )
    assert result.exit_code == 0
    assert called["url"] == "http://127.0.0.1:8087/check-access"


def test_model_file_loader_supports_yaml() -> None:
    schema = load_authorization_model_from_file("examples/auth-model.yaml")
    assert "model schema 1" in schema
    assert "read = owner or editor" in schema


def test_single_file_policy_loader_works() -> None:
    policies = load_policies_from_file("examples/policies/ops_rules.polar")
    assert len(policies) == 2
