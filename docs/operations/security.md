# Security

KeyNetra ships with release guardrails focused on authorization correctness and secure defaults.

## Authentication

- API keys
- hashed API keys
- JWT bearer tokens
- optional OIDC JWKS validation

## Runtime Guardrails

- production rejects weak default JWT secret
- production rejects SQLite
- production requires at least one auth method
- strict tenancy can force explicit tenant routing
- errors return structured envelopes instead of raw traces

## Cache Safety

- local caches are bounded
- distributed cache remains optional
- cache keys are based on explicit hydrated input

## Secrets Handling

- run `detect-secrets-hook --baseline .secrets.baseline`
- keep runtime secrets in env vars, secret managers, or Kubernetes Secrets
- do not commit API keys or JWT secrets

## Security References

- repository policy: [SECURITY.md](../../SECURITY.md)
- CI runs Bandit, secret scanning, and dependency auditing
