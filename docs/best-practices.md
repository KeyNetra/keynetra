# Best Practices

## 1) Deny by default

Treat unmatched requests as deny.
Do not create broad fallback allow rules.

## 2) Apply least privilege

- Grant only required actions
- Prefer narrower resource scopes
- Review and remove stale grants regularly

## 3) Use policy versioning discipline

- Track policy changes in source control
- Require review for policy edits
- Use `policy_id` naming that reflects intent and version

## 4) Keep tenant boundaries explicit

- Include tenant checks in policies/attributes
- Prevent cross-tenant reads by default
- Test multi-tenant edge cases with batch checks

## 5) Validate before deployment

Always run both:

- `/simulate-policy` for before/after behavior
- `/impact-analysis` for affected user scope

## 6) Use explainability in production support

Persist or log these fields from decisions:

- `decision`
- `reason`
- `policy_id`
- `revision`
- `explain_trace`

## 7) Keep ACL usage controlled

Use ACL for explicit exceptions, not as the primary model for the whole system.

## 8) Add policy tests for critical flows

- Payment approvals
- Admin operations
- Cross-tenant access
- Data export operations
