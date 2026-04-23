# Authorization Models

KeyNetra supports several authorization styles in one runtime.

## RBAC

Role-based access control grants permissions through user roles.

Example:

```json
{
  "user": {"id": "u1", "role": "admin", "roles": ["admin"]},
  "action": "read",
  "resource": {"resource_type": "document", "resource_id": "doc-1"}
}
```

Use RBAC when:

- permissions are mostly role-driven
- the role catalog is stable
- you want simple operator workflows

## ABAC

Attribute-based access control evaluates request attributes using policy conditions.

Example policy:

```json
{
  "action": "approve_payment",
  "effect": "allow",
  "priority": 10,
  "conditions": {
    "role": "manager",
    "max_amount": 1000
  }
}
```

Use ABAC when:

- rules depend on resource or request context
- you need constraints like amount, region, or time windows

## ACL

Access control lists store explicit allow/deny entries on resources.

Example:

```bash
keynetra acl add \
  --subject-type user \
  --subject-id u1 \
  --resource-type document \
  --resource-id doc-1 \
  --action read \
  --effect allow
```

Use ACL when:

- operators need explicit grants on individual resources
- resource ownership is highly dynamic

## Relationship-Based Access Control

Relationship checks use subject/object edges such as `viewer`, `owner`, or `member_of`.

Example relationship:

```json
{
  "subject_type": "user",
  "subject_id": "u1",
  "relation": "viewer",
  "object_type": "document",
  "object_id": "doc-1"
}
```

Use relationship-based access when:

- access depends on membership, ownership, or delegation graphs
- documents, teams, folders, or tenants have graph-shaped permissions

## Combining Models

KeyNetra does not force a single strategy. A request may hit:

- RBAC first for broad grants
- ACL for resource-specific overrides
- relationship index for graph matches
- ABAC policies for context-sensitive rules

That combination is what makes explain traces important.
