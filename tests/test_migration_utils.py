from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from keynetra.config.settings import reset_settings_cache
from keynetra.migrations import find_destructive_revisions


def test_find_destructive_revisions(tmp_path: Path) -> None:
    revision_file = tmp_path / "20260405_drop.py"
    revision_file.write_text("""from alembic import op

revision = "20260405_drop"
down_revision = "20260404_000005"

def upgrade():
    op.drop_table("old_table")
""")

    pending = find_destructive_revisions(tmp_path, applied_revisions={"20260404_000005"})
    assert pending == ["20260405_drop"]


def test_initial_migration_uses_explicit_ops_not_metadata_shortcuts() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260407_000001_initial_schema_v0.py"
    ).read_text(encoding="utf-8")

    assert "create_all" not in migration
    assert "drop_all" not in migration
    assert "op.create_table" in migration


def test_migration_roundtrip_creates_and_drops_schema(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'roundtrip.db'}"
    os.environ["KEYNETRA_DATABASE_URL"] = database_url
    reset_settings_cache()
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    inspector = inspect(create_engine(database_url, future=True))
    assert "tenants" in inspector.get_table_names()
    assert "audit_logs" in inspector.get_table_names()
    assert "idempotency_records" in inspector.get_table_names()

    command.downgrade(config, "base")
    inspector = inspect(create_engine(database_url, future=True))
    assert "tenants" not in inspector.get_table_names()
