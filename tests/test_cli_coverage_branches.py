from __future__ import annotations

import json
import os

from keynetra.cli import app
from keynetra.config.settings import get_settings, reset_settings_cache
from typer.testing import CliRunner


def test_compile_policies_reports_missing_paths(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        "keynetra.cli.get_settings",
        lambda: type("S", (), {"parsed_policy_paths": lambda self: []})(),
    )  # type: ignore[misc]
    result = runner.invoke(app, ["compile-policies"])
    assert result.exit_code == 2


def test_compile_policies_reports_missing_definitions(monkeypatch, tmp_path) -> None:
    runner = CliRunner()
    empty_dir = tmp_path / "empty-policies"
    empty_dir.mkdir()
    result = runner.invoke(app, ["compile-policies", "--path", str(empty_dir)])
    assert result.exit_code == 2


def test_doctor_core_failure_returns_exit_1(monkeypatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(
        "keynetra.cli.run_core_doctor", lambda settings: {"ok": False, "errors": ["x"]}
    )
    result = runner.invoke(app, ["doctor", "--service", "core"])
    assert result.exit_code == 1
    assert '"ok": false' in result.stdout.lower()


def test_doctor_invalid_service_is_rejected() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--service", "invalid"])
    assert result.exit_code == 2


def test_benchmark_validation_and_empty_samples(monkeypatch) -> None:
    runner = CliRunner()

    bad_requests = runner.invoke(app, ["benchmark", "--api-key", "k", "--requests", "0"])
    assert bad_requests.exit_code == 2

    bad_concurrency = runner.invoke(app, ["benchmark", "--api-key", "k", "--concurrency", "0"])
    assert bad_concurrency.exit_code == 2

    async def _empty_benchmark(*args, **kwargs):
        return []

    monkeypatch.setattr("keynetra.cli._run_benchmark", _empty_benchmark)
    empty = runner.invoke(
        app, ["benchmark", "--api-key", "k", "--requests", "1", "--concurrency", "1"]
    )
    assert empty.exit_code == 1
    assert "No successful samples collected." in empty.stdout


def test_acl_add_list_remove_commands(tmp_path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'acl-cli.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    reset_settings_cache()
    get_settings.cache_clear()
    runner = CliRunner()

    created = runner.invoke(
        app,
        [
            "acl",
            "add",
            "--subject-type",
            "user",
            "--subject-id",
            "u1",
            "--resource-type",
            "document",
            "--resource-id",
            "doc-1",
            "--action",
            "read",
            "--effect",
            "allow",
        ],
    )
    assert created.exit_code == 0
    payload = json.loads(created.stdout)
    acl_id = payload["acl_id"]

    listed = runner.invoke(
        app,
        [
            "acl",
            "list",
            "--resource-type",
            "document",
            "--resource-id",
            "doc-1",
        ],
    )
    assert listed.exit_code == 0
    entries = json.loads(listed.stdout)
    assert entries and entries[0]["id"] == acl_id

    removed = runner.invoke(app, ["acl", "remove", "--acl-id", str(acl_id)])
    assert removed.exit_code == 0
    removed_payload = json.loads(removed.stdout)
    assert removed_payload["acl_id"] == acl_id


def test_main_entrypoint_invokes_typer_app(monkeypatch) -> None:
    called = {"value": False}

    def fake_app() -> None:
        called["value"] = True

    monkeypatch.setattr("keynetra.cli.app", fake_app)

    from keynetra.cli import main

    main()
    assert called["value"] is True
