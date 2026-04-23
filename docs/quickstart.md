# Quickstart

This guide starts KeyNetra locally and sends a real authorization request against the API.

## 1. Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

## 2. Start The API

Use a local SQLite database and a development API key:

```bash
export KEYNETRA_DATABASE_URL=sqlite+pysqlite:///./keynetra-quickstart.db
export KEYNETRA_API_KEYS=devkey
export KEYNETRA_API_KEY_SCOPES_JSON='{"devkey":{"tenant":"default","role":"admin","permissions":["*"]}}'
export KEYNETRA_RATE_LIMIT_DISABLED=true

keynetra serve --host 127.0.0.1 --port 8080
```

In development mode, KeyNetra bootstraps the default tenant automatically.

## 3. Verify Health

```bash
curl -i http://127.0.0.1:8080/health/ready
```

Expected result: HTTP `200` with a JSON payload containing `"status":"ok"`.

## 4. Run An Authorization Check

```bash
curl -s -X POST http://127.0.0.1:8080/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "action": "read",
    "resource": {
      "resource_type": "document",
      "resource_id": "doc-1",
      "id": "doc-1"
    },
    "context": {}
  }'
```

Example response:

```json
{
  "data": {
    "allowed": true,
    "decision": "allow",
    "matched_policies": [],
    "reason": "explicit permission grant",
    "policy_id": "rbac:permissions",
    "explain_trace": [],
    "revision": 1
  },
  "meta": {
    "request_id": "..."
  },
  "error": null
}
```

## 5. Inspect The CLI

```bash
keynetra --help
keynetra version
keynetra help-cli
```

## 6. Generate OpenAPI

```bash
keynetra generate-openapi --output docs/openapi.json
keynetra check-openapi --contract docs/openapi.json
```

## Next Steps

- Read [Configuration](configuration.md) for environment variables and config files.
- Read [Authorization Models](authorization-models.md) to choose RBAC, ABAC, ACL, or ReBAC patterns.
- Read [Docker Deployment](deployment/docker.md) if you want to run KeyNetra in containers.
