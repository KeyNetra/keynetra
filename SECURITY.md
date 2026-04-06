# Security Policy

## Reporting vulnerabilities

Do not open public issues for security findings.

Report privately to:

- `security@keynetra.com`

Include:

- affected component/endpoint
- reproduction steps
- potential impact
- suggested mitigation (if available)

## Safe policy design recommendations

1. Default deny

- Do not rely on broad allow fallback policies.

2. Least privilege

- Grant only required actions for each role.

3. Separate duties

- Add explicit deny controls for high-risk flows (for example maker-checker).

4. Tenant isolation

- Enforce tenant boundaries in policy and request attributes.

5. Validate policy changes before rollout

- Use `/simulate-policy` for before/after decision checks.
- Use `/impact-analysis` to detect large blast radius.

6. Audit decision metadata

- Store `decision`, `reason`, `policy_id`, and `revision` for traceability.

## Supported versions

Security fixes are applied to the current active release line.
