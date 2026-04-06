---
title: Contributing
---

# Contributing

Primary contribution guidance comes from:

- `CONTRIBUTING.md`

## Standards

- Python 3.11
- Black formatting
- Isort import order
- Ruff lint rules
- tests and coverage maintained
- architecture boundaries respected (`keynetra/` does not depend on `infra/`)

## Documentation Expectations

- update docs for behavior changes
- keep examples runnable and version-aligned
- maintain internal links across pages

## Typical Workflow

1. Create branch
2. Implement focused change
3. Add/update tests
4. Run lint + tests
5. Update docs/migrations as needed
6. Open PR

## Useful Commands

```bash
make lint
make test
make migrate
```

## Related Pages

- [Local Development](local-development.md)
- [CI/CD and Release](ci-cd-release.md)
- [Testing Strategy](testing.md)
