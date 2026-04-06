#!/usr/bin/env bash
set -euo pipefail

API_KEY="${API_KEY:-testkey}"
BASE_URL="${BASE_URL:-http://localhost:8000}"

keynetra check \
  --api-key "$API_KEY" \
  --url "$BASE_URL/check-access" \
  --user '{"id":"alice","role":"editor","permissions":["approve_payment"]}' \
  --action read \
  --resource '{"resource_type":"document","resource_id":"doc-123"}' \
  --context '{"department":"engineering"}'

keynetra simulate \
  --api-key "$API_KEY" \
  --url "$BASE_URL/simulate-policy" \
  --policy-change 'allow:\n  action: share_document\n  priority: 1\n  policy_key: share-admin\n  when:\n    role: admin' \
  --user '{"id":"root-admin","role":"admin","roles":["admin"]}' \
  --action share_document \
  --resource '{"resource_type":"document","resource_id":"doc-123"}'

keynetra impact \
  --api-key "$API_KEY" \
  --url "$BASE_URL/impact-analysis" \
  --policy-change 'deny:\n  action: export_payment\n  priority: 1\n  policy_key: deny-export-contractors\n  when:\n    role: external'

keynetra test-policy examples/policy_tests.yaml
keynetra compile-policies --path examples/policies/document_access.yaml --path examples/policies/finance_policy.yaml
