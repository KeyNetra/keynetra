# Contributing to KeyNetra

Thanks for contributing.
This guide is optimized for first-time contributors.

## Development setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
export KEYNETRA_API_KEYS=devkey
```

Start the API locally:

```bash
python -m keynetra.cli serve
```

## Run tests

Run all tests:

```bash
PYTHONPATH=. python3.11 -m pytest -q
```

Run targeted tests:

```bash
PYTHONPATH=. python3.11 -m pytest -q tests/test_api.py
```

## Coding guidelines

- Keep changes small and focused
- Add tests for behavior changes
- Keep documentation in sync with code
- Prefer clear names over clever shortcuts
- Do not add unrelated refactors in the same PR

Formatting/linting tools used in this project:

- `black`
- `isort`
- `ruff`

## Pull request checklist

1. Create a feature branch
2. Implement change with tests
3. Run test suite locally
4. Update docs when behavior changes
5. Open PR with clear summary:
   - problem
   - approach
   - test evidence

## Reporting bugs

When opening an issue, include:

- expected behavior
- actual behavior
- minimal reproducible request/payload
- logs/error output
- runtime info (Python version, OS)
