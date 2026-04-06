# ABAC (Attribute-Based Access Control)

ABAC evaluates attributes from user, resource, and context.

## Simple idea

A request is allowed when conditions match attributes.

Examples of attributes:

- User: `department`, `employment_type`
- Resource: `owner_id`, `classification`, `amount`
- Context: `time`, `ip`, `region`

## Example

Policy condition concept:

```yaml
conditions:
  role: manager
  max_amount: 100000
```

Request resource:

```json
{"amount": 45000}
```

Result: allowed for a manager under threshold.

## When ABAC works well

- Financial approvals
- Geo/time-based restrictions
- Department-scoped access
