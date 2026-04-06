---
title: Policy Patterns
---

# Policy Patterns

These patterns are aligned with KeyNetra policy parsing and decision priority behavior.

## Pattern 1: Explicit Admin Allow

```yaml
policies:
  - policy_id: allow-read-admin
    action: read
    effect: allow
    priority: 20
    conditions:
      role: admin
```

Use when a role should have stable baseline access.

## Pattern 2: Deny Override for High-Risk Context

```yaml
policies:
  - policy_id: deny-export-external
    action: export
    effect: deny
    priority: 100
    conditions:
      role: external
```

Use high priority deny rules for risk boundaries.

## Pattern 3: Amount Guardrail

```yaml
policies:
  - policy_id: allow-approve-manager-low-value
    action: approve_payment
    effect: allow
    priority: 40
    conditions:
      role: manager
      max_amount: 10000
```

Pair with request payload context such as `amount` to enforce transaction limits.

## Pattern 4: Department Scope

```yaml
policies:
  - policy_id: allow-finance-read
    action: read_payment
    effect: allow
    priority: 30
    conditions:
      department: finance
```

Use contextual fields from `context` payload for scoped permissions.

## Pattern 5: Progressive Rollout

1. Create policy in low priority allow mode.
2. Run `simulate-policy` for representative users/resources.
3. Run `impact-analysis` to estimate changed decisions.
4. Increase priority after validation.

## Validation Checklist

- Every rule has an explicit `action`, `effect`, and `priority`.
- `policy_id` or `policy_key` is stable for rollback/audit.
- Condition keys match request schema fields.
- Run `compile-policies` and `test-policy` before deployment.

## Related Pages

- [Policy File Formats](../reference/policy-files.md)
- [CLI Workflows](cli-workflows.md)
- [End-to-End API Flow](end-to-end-api-flow.md)
