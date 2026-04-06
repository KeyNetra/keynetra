from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytest.importorskip("typer")
from keynetra.cli import app
from keynetra.config.settings import Settings, reset_settings_cache
from keynetra.services.doctor import run_core_doctor
from typer.testing import CliRunner


class _FakeRedis:
    def ping(self) -> bool:
        return True


def _set_core_env(database_url: str) -> None:
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ["KEYNETRA_REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["KEYNETRA_API_KEYS"] = "test-key"
    reset_settings_cache()


def _prepare_alembic_version(database_url: str, revision: str) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": revision},
        )


def test_run_core_doctor_reports_all_checks_healthy(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path}/core-doctor.db"
    _set_core_env(database_url)
    _prepare_alembic_version(database_url, "20260407_000001")
    monkeypatch.setattr("keynetra.services.doctor.get_redis", lambda: _FakeRedis())

    result = run_core_doctor(Settings())

    assert result["service"] == "core"
    assert result["ok"] is True
    assert {check["name"]: check["ok"] for check in result["checks"]} == {
        "env_variables": True,
        "database": True,
        "redis": True,
        "migrations": True,
    }


def test_cli_doctor_exits_nonzero_when_core_is_not_ready(
    tmp_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path}/core-not-ready.db"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    os.environ.pop("KEYNETRA_REDIS_URL", None)
    os.environ.pop("KEYNETRA_API_KEYS", None)
    os.environ["KEYNETRA_JWT_SECRET"] = "change-me"
    reset_settings_cache()
    monkeypatch.setattr("keynetra.services.doctor.get_redis", lambda: None)

    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--service", "core"])

    assert result.exit_code == 1
    assert '"service": "core"' in result.output
