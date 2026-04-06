---
title: CI/CD and Release
---

# CI/CD and Release

GitHub Actions workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

## CI Workflow

Triggered on pushes and pull requests.

Stages:

1. Setup Python 3.11
2. Install dependencies
3. Lint (`ruff`, `black --check`, `isort --check-only`)
4. Migration check (`python -m keynetra.cli migrate --confirm-destructive`)
5. Tests + coverage (`--cov-fail-under=80`)

CI currently runs on Python 3.11.

## Release Workflow

Triggered on tags matching `v*`.

Stages:

1. Build package (`python -m build`)
2. Run tests with coverage
3. Upload artifacts (`.whl`, `.tar.gz`)
4. Publish GitHub release

## Recommended Release Steps

1. ensure version alignment (`pyproject.toml`, `keynetra/version.py`, OpenAPI info)
2. run lint, migrations, and full tests locally
3. confirm changelog and release notes
4. push release tag (`vX.Y.Z`)

## Version and Contract Alignment

Version `0.1.0` is currently represented in:

- `pyproject.toml`
- `keynetra/version.py`
- `contracts/openapi/keynetra-v0.1.0.yaml`

## Release Hygiene Checklist

- tests pass locally and in CI
- OpenAPI contract synced with implemented routes
- migrations apply cleanly
- docs and examples updated
- changelog updated

## Related Pages

- [Testing Strategy](testing.md)
- [Contributing](contributing.md)
- [Migrations](migrations.md)
