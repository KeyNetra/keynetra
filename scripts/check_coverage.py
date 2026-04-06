#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

STRICT_ENV = "STRICT_MODULE_COVERAGE"

MODULE_MINIMUMS = {
    "keynetra/services/authorization.py": 85.0,
    "keynetra/config/security.py": 80.0,
    "keynetra/api/routes/access.py": 85.0,
}


def main() -> int:
    path = Path("coverage.json")
    if not path.exists():
        print("coverage.json not found; run pytest with --cov-report=json")
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    files = payload.get("files", {})
    failures: list[str] = []
    for file_path, minimum in MODULE_MINIMUMS.items():
        metrics = files.get(file_path)
        if not isinstance(metrics, dict):
            failures.append(f"{file_path}: missing from coverage report")
            continue
        summary = metrics.get("summary", {})
        pct = float(summary.get("percent_covered", 0.0))
        if pct < minimum:
            failures.append(f"{file_path}: {pct:.2f}% < minimum {minimum:.2f}%")
    if failures:
        print("module coverage thresholds failed:")
        for failure in failures:
            print(f" - {failure}")
        if os.environ.get(STRICT_ENV, "0") == "1":
            return 1
        print(f"notice: set {STRICT_ENV}=1 to enforce module percentage gates")
        return 0
    print("module coverage thresholds passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
