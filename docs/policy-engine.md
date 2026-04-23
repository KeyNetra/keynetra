# Policy Engine

KeyNetra’s policy engine is deterministic and side-effect free.

## Input Contract

The engine evaluates a single `AuthorizationInput` containing:

- `user`
- `action`
- `resource`
- `context`
- optional ACL entries
- optional relationship/access-index entries
- optional compiled authorization model

## Policy Shape

```json
{
  "action": "read",
  "effect": "allow",
  "priority": 10,
  "policy_id": "document-read-admin",
  "conditions": {
    "role": "admin"
  }
}
```

## Supported Condition Types

- `role`
- `max_amount`
- `owner_only`
- `time_range`
- `geo_match`
- `has_relation`

## Evaluation Behavior

- Lower `priority` wins first because policies are sorted before execution.
- Matching `allow` or `deny` policies terminate evaluation.
- No match falls through to default deny.
- Explain traces record each stage and the winning policy id when present.

## Compile And Validate Policies

```bash
keynetra compile-policies --path examples/policies
keynetra test-policy examples/policy_tests.yaml
```

## Simulate Changes

```bash
keynetra simulate \
  --api-key devkey \
  --policy-change '{"action":"read","effect":"deny","priority":1,"conditions":{}}' \
  --action read
```

## Impact Analysis

```bash
keynetra impact \
  --api-key devkey \
  --policy-change '{"action":"read","effect":"deny","priority":1,"conditions":{}}'
```

## Design Principles

- no hidden network or database access in the engine
- explicit input hydration in the service layer
- cache results outside the engine, not inside it
- prefer explainability over opaque optimization
