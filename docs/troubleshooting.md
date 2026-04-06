# Troubleshooting

## 1) `401 unauthorized` on every request

Cause:

- Missing or wrong API key

Fix:

```bash
export KEYNETRA_API_KEYS=devkey
curl -H "X-API-Key: devkey" http://localhost:8000/health
```

## 2) `403 forbidden` on simulation endpoints

Cause:

- Principal does not have required management role

Fix:

- Use API key auth for local testing (`X-API-Key`)
- Or provide JWT with management claims

## 3) `429 too_many_requests`

Cause:

- Rate limit exceeded

Fix:

```bash
export KEYNETRA_RATE_LIMIT_PER_MINUTE=1000
export KEYNETRA_RATE_LIMIT_BURST=1000
```

## 4) Database errors at startup

Cause:

- Bad `KEYNETRA_DATABASE_URL`
- Missing local DB permissions

Fix:

```bash
export KEYNETRA_DATABASE_URL=sqlite+pysqlite:///./keynetra.db
python -m keynetra.cli serve
```

## 5) Policy change does not seem to apply

Cause:

- Cache still serving old state
- Policy not loaded from expected path

Fix:

- Confirm policy path/config values
- Restart server for local debugging
- Use `/simulate-policy` to confirm new policy behavior

## 6) Hard to understand deny responses

Fix:

- Use `/simulate` for `failed_conditions`
- Inspect `reason`, `policy_id`, and `explain_trace`

## 7) CLI command cannot find model/policy file

Fix:

- Use absolute paths first
- Confirm working directory is repository root
- Check file extension and content format
