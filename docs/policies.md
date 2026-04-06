# Policy Guide

This guide explains policy structure in plain language.

## Policy structure

Key fields you will use most:

- `action`: what operation the policy targets
- `effect`: `allow` or `deny`
- `priority`: lower numbers are evaluated first
- `policy_id` (or key): identifier shown in decision responses
- `conditions`: attribute checks required for a match

## Example

```yaml
policies:
  - action: approve_payment
    effect: allow
    priority: 10
    policy_id: finance-approve-manager-under-limit
    conditions:
      role: manager
      max_amount: 100000

  - action: approve_payment
    effect: deny
    priority: 20
    policy_id: finance-maker-checker-deny
    conditions:
      owner_only: true
```

## Allow and deny logic

- Policies are checked by priority.
- First matching policy determines outcome.
- If nothing matches, system returns deny (safe default).

## Priority rules

- Smaller number = higher priority
- Use this to place explicit safety denies before broad allows

Example:

- Priority `1`: deny risky operation
- Priority `10`: allow common trusted flow

## Conditions and attributes

Conditions are matched against request data:

- `user` attributes (`role`, `permissions`)
- `resource` attributes (`amount`, `owner_id`, `resource_type`)
- `context` attributes (`department`, `time`)

## Practical tips

- Keep policies small and focused
- Use clear `policy_id` names so traces are readable
- Prefer explicit denies for high-risk operations
- Validate changes with `/simulate-policy` before deployment
- Run `/impact-analysis` for high-blast-radius updates

## Example workflow

1. Draft policy in YAML
2. Run `python -m keynetra.cli test-policy <file>`
3. Run `/simulate-policy` with representative request
4. Run `/impact-analysis` to measure user impact
5. Deploy policy
