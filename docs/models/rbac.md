# RBAC (Role-Based Access Control)

RBAC grants access based on roles assigned to users.

## Simple idea

- Users have roles (`admin`, `manager`, `viewer`)
- Roles map to allowed actions

## Example

User:

```json
{"id": "alice", "role": "manager", "permissions": ["approve_payment"]}
```

Request:

```json
{"action": "approve_payment"}
```

If the role/permissions include the action, decision is `allow`.

## When RBAC works well

- Standard SaaS dashboards
- Internal admin tooling
- Stable permission catalogs

## Limitation

RBAC alone cannot express dynamic constraints like "amount < 100000".
Use ABAC for that.
