from __future__ import annotations

from pathlib import Path

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
