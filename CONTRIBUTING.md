# Contributing to KeyNetra

KeyNetra targets Python 3.11 and keeps the core release workflow intentionally simple:

- `make install`
- `make test`
- `make lint`
- `make format`
- `make migrate`
- `make run`

## Development Setup

1. Create and activate a virtual environment.
2. Install dependencies with `make install`.
3. Set any required environment variables in `.env`.
4. Start the API with `make run` or `uvicorn keynetra.api.main:app`.

## Running Tests

Run the full test suite with:

```bash
make test
```

Run coverage checks with:

```bash
pytest -q --cov=keynetra --cov-fail-under=80
```

## Migration Workflow

Use the local migration command when schema changes are needed:

```bash
make migrate
```

If you are applying a destructive migration on purpose, pass the confirmation flag through the CLI:

```bash
python -m keynetra.cli migrate --confirm-destructive
```

## Coding Standards

- Format Python with `black`
- Sort imports with `isort`
- Keep lint clean with `ruff`
- Prefer small, focused changes with tests
- Avoid coupling the `keynetra/` package to `infra/`

## Pull Request Process

1. Open a feature branch.
2. Add or update tests for behavioral changes.
3. Run `make lint` and `make test` locally.
4. Update docs or migrations when relevant.
5. Use the pull request template and complete the checklist.
