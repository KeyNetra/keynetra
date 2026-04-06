# KeyNetra Verification Guide

This guide verifies KeyNetra end-to-end without any UI.

## 1) Run the test suite

```bash
PYTHONPATH=. python3.11 -m pytest -q
```

Coverage audited in `tests/` (the repository does not contain `core/tests/`):

- authorization engine
- RBAC, ABAC, ACL, relationship-based access (ReBAC)
- authorization modeling and compiled policy evaluation
- policy simulation and impact analysis
- revision tokens and consistency behavior
- metrics endpoint and cache behavior
- API contracts

Additional endpoint-level coverage added for:

- `POST /check-access-batch`
- `POST /simulate`
- `POST /simulate-policy`
- `POST /impact-analysis`

## 2) Real-world authorization scenarios

Use:

- `examples/scenarios/real_world_authorization_scenarios.yaml`

Included scenarios:

- Document management system
- SaaS multi-tenant access
- Financial approval workflow
- Team collaboration
- Admin privilege delegation

Each scenario defines subjects, resources, actions, relationships, roles, policies, and ACL entries.

## 3) Authorization models

Use model examples from:

- `examples/models/document_model.yaml`
- `examples/models/saas_tenant_model.yaml`
- `examples/models/finance_model.yaml`
- `examples/models/team_collaboration_model.yaml`
- `examples/models/admin_delegation_model.yaml`

## 4) Policy examples

Use policy files from:

- `examples/policies/document_access.yaml`
- `examples/policies/finance_policy.yaml`
- `examples/policies/team_access.yaml`

## 5) API request examples

Request payloads for all required endpoints:

- `examples/requests/api_requests.json`

Expected responses:

- `examples/responses/api_expected_responses.json`

### Example calls

```bash
curl -s -X POST http://localhost:8000/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: testkey" \
  -d @<(jq '.["check-access"]' examples/requests/api_requests.json)

curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: testkey" \
  -d @<(jq '.["check-access-batch"]' examples/requests/api_requests.json)

curl -s -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: testkey" \
  -d @<(jq '.["simulate"]' examples/requests/api_requests.json)

curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: testkey" \
  -d @<(jq '.["simulate-policy"]' examples/requests/api_requests.json)

curl -s -X POST http://localhost:8000/impact-analysis \
  -H "Content-Type: application/json" \
  -H "X-API-Key: testkey" \
  -d @<(jq '.["impact-analysis"]' examples/requests/api_requests.json)
```

## 6) CLI verification examples

Use:

- `examples/requests/cli_examples.sh`

Direct commands:

```bash
keynetra check \
  --api-key testkey \
  --user '{"id":"alice","role":"editor","permissions":["approve_payment"]}' \
  --action read \
  --resource '{"resource_type":"document","resource_id":"doc-123"}'

keynetra simulate \
  --api-key testkey \
  --policy-change 'allow:\n  action: share_document\n  priority: 1\n  policy_key: share-admin\n  when:\n    role: admin' \
  --user '{"id":"root-admin","role":"admin","roles":["admin"]}' \
  --action share_document \
  --resource '{"resource_type":"document","resource_id":"doc-123"}'

keynetra impact \
  --api-key testkey \
  --policy-change 'deny:\n  action: export_payment\n  priority: 1\n  policy_key: deny-export-contractors\n  when:\n    role: external'
```

## 7) Developer verification forms

Use structured forms from:

- `examples/forms/developer_verification_forms.json`

Fill one form per test case and compare actual decision vs `expected`.

## 8) Example test datasets

Use these datasets to seed and validate real-world flows:

- `examples/data/users.json`
- `examples/data/roles.json`
- `examples/data/relationships.json`
- `examples/data/acl_entries.json`

## 9) No-UI developer workflow

1. Start API: `keynetra serve`
2. Run tests: `PYTHONPATH=. python3.11 -m pytest -q`
3. Replay API payloads from `examples/requests/api_requests.json`
4. Compare responses to `examples/responses/api_expected_responses.json`
5. Run CLI checks from `examples/requests/cli_examples.sh`
6. Validate scenario decisions using `examples/forms/developer_verification_forms.json`

This provides repeatable verification through API, CLI, config files, and datasets only.
