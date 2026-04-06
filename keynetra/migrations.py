"""Utilities for detecting destructive Alembic migrations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

DROP_PATTERN = re.compile(r"\bdrop_(?:table|column)\b")
REVISION_PATTERN = re.compile(r"^revision\s*=\s*['\"](?P<revision>[^'\"]+)['\"]", re.MULTILINE)


def parse_revision_file(path: Path) -> tuple[str | None, bool]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, False
    match = REVISION_PATTERN.search(content)
    revision = match.group("revision") if match else None
    destructive = bool(DROP_PATTERN.search(content))
    return revision, destructive


def find_destructive_revisions(versions_dir: Path, applied_revisions: Iterable[str]) -> list[str]:
    applied = {rev for rev in applied_revisions if isinstance(rev, str)}
    destructive: list[str] = []
    for path in versions_dir.glob("*.py"):
        revision, has_drop = parse_revision_file(path)
        if revision and has_drop and revision not in applied:
            destructive.append(revision)
    return sorted(destructive)
