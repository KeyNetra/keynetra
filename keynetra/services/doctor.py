"""Production-readiness checks for the KeyNetra core service.

These checks stay in the services layer because they orchestrate infrastructure
dependencies such as the database, Redis, and Alembic migration state.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings
from keynetra.infrastructure.storage.session import create_engine_for_url


@dataclass(frozen=True)
class DoctorCheck:
    """One production-readiness validation result."""

    name: str
    ok: bool
    message: str
    details: dict[str, Any]


def run_core_doctor(settings: Settings) -> dict[str, Any]:
    """Run deterministic readiness checks for the core deployment."""

    checks = [
        _check_env(settings),
        _check_database(settings),
        _check_redis(),
        _check_migrations(settings),
    ]
    return {
        "service": "core",
        "ok": all(check.ok for check in checks),
        "checks": [asdict(check) for check in checks],
    }


def _check_env(settings: Settings) -> DoctorCheck:
    """Validate that the required runtime configuration is explicitly set."""

    required_env = {
        "KEYNETRA_DATABASE_URL": bool(os.environ.get("KEYNETRA_DATABASE_URL")),
        "KEYNETRA_REDIS_URL": bool(os.environ.get("KEYNETRA_REDIS_URL")),
    }
    auth_configured = (
        bool(settings.parsed_api_key_hashes())
        or settings.jwt_secret != "change-me"
        or bool(settings.oidc_jwks_url)
    )
    ok = all(required_env.values()) and auth_configured
    return DoctorCheck(
        name="env_variables",
        ok=ok,
        message=(
            "required environment is configured"
            if ok
            else "missing required environment configuration"
        ),
        details={**required_env, "auth_configured": auth_configured},
    )


def _check_database(settings: Settings) -> DoctorCheck:
    """Verify that the configured primary database accepts queries."""

    try:
        engine = create_engine_for_url(settings.database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return DoctorCheck(
            name="database",
            ok=True,
            message="database reachable",
            details={"database_url": settings.database_url},
        )
    except SQLAlchemyError as exc:
        return DoctorCheck(
            name="database", ok=False, message="database unreachable", details={"error": repr(exc)}
        )


def _check_redis() -> DoctorCheck:
    """Verify that the configured Redis endpoint responds to ping."""

    client = get_redis()
    if client is None:
        return DoctorCheck(
            name="redis", ok=False, message="redis client not configured", details={}
        )
    try:
        client.ping()
        return DoctorCheck(name="redis", ok=True, message="redis reachable", details={})
    except Exception as exc:
        return DoctorCheck(
            name="redis", ok=False, message="redis unreachable", details={"error": repr(exc)}
        )


def _check_migrations(settings: Settings) -> DoctorCheck:
    """Verify that the database is at the current Alembic head revision."""

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    core_dir = Path(__file__).resolve().parents[2]
    config = Config(str(core_dir / "alembic.ini"))
    config.set_main_option("script_location", str(core_dir / "alembic"))
    script = ScriptDirectory.from_config(config)
    expected_heads = sorted(script.get_heads())
    try:
        engine = create_engine_for_url(settings.database_url)
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        applied_heads = sorted(str(row[0]) for row in rows)
    except Exception as exc:
        return DoctorCheck(
            name="migrations",
            ok=False,
            message="could not read migration state",
            details={"error": repr(exc)},
        )

    ok = applied_heads == expected_heads
    return DoctorCheck(
        name="migrations",
        ok=ok,
        message="migrations applied" if ok else "database is not at migration head",
        details={"expected_heads": expected_heads, "applied_heads": applied_heads},
    )
