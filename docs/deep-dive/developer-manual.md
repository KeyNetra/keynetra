# Developer Manual (Detailed)

This manual explains how KeyNetra works from request entry to final decision.
It is intended for developers integrating KeyNetra into real services.

## 1) Mental model

At runtime, KeyNetra does this for every authorization check:

1. Accept request from API or CLI
2. Authenticate principal (`X-API-Key` or JWT)
3. Build normalized `AuthorizationInput`
4. Enrich user/resource context (roles, permissions, relationships)
5. Evaluate decision using deterministic engine stages
6. Return decision envelope with reason and explain trace

Core types:

- `AuthorizationInput` in `keynetra/engine/keynetra_engine.py`
- `AuthorizationDecision` in `keynetra/engine/keynetra_engine.py`
- `AuthorizationResult` in `keynetra/services/authorization.py`

## 2) API entry points and code path

Main route handlers:

- `POST /check-access` -> `keynetra/api/routes/access.py::check_access`
- `POST /check-access-batch` -> `keynetra/api/routes/access.py::check_access_batch`
- `POST /simulate` -> `keynetra/api/routes/access.py::simulate`
- `POST /simulate-policy` -> `keynetra/api/routes/simulation.py::simulate_policy`
- `POST /impact-analysis` -> `keynetra/api/routes/simulation.py::impact_analysis`

Service construction:

- `get_authorization_service()` wires repositories + caches in `access.py`
- `get_simulation_services()` wires simulator/analyzer in `simulation.py`

## 3) AuthorizationService internals

File: `keynetra/services/authorization.py`

Primary methods:

- `authorize(...)`
- `authorize_batch(...)`
- `simulate(...)`
- `get_revision(...)`

### 3.1 `authorize(...)` flow

`authorize()` does more than engine evaluation. It orchestrates:

1. Input validation via `validate_user` and `validate_resource`
2. Tenant lookup via `TenantRepository`
3. User hydration (`_hydrate_user`) to include persisted roles/relationships
4. Decision cache lookup (unless `consistency=fully_consistent`)
5. Engine construction (`_build_engine`) using current policy version
6. Pure engine call: `engine.decide(authorization_input)`
7. Cache write, audit write, and metrics reporting
8. Resilience fallback if dependencies fail

Why this matters:

- API behavior is stable even when cache or storage temporarily fails
- Decisions remain explainable because fallback still returns structured traces

### 3.2 `authorize_batch(...)`

`authorize_batch()`:

- Reuses tenant and engine setup once
- Evaluates items concurrently using `ThreadPoolExecutor`
- Preserves per-item allow/deny results with revision

Use this when frontends need many permission checks in one request.

### 3.3 `simulate(...)`

`simulate()` calls `authorize()` and returns `decision` directly.

Key difference from `/check-access`:

- API response includes `failed_conditions` and trace details for diagnostics

### 3.4 How input enrichment works

`_hydrate_user(...)` adds:

- `roles`
- `role_permissions`
- `relations`
- `direct_permissions`

This enables mixed RBAC/ABAC/ReBAC decisions from one normalized input.

## 4) Engine internals and stage ordering

File: `keynetra/engine/keynetra_engine.py`

`KeyNetraEngine._decide_structured(...)` evaluates in fixed order:

1. Direct permissions (`rbac:permissions`)
2. ACL match
3. Role permissions (`rbac:role`)
4. Relationship index check (`relationship:index`)
5. Compiled authorization model graph (`permission_graph`)
6. Compiled policy graph (`policy_graph`)
7. Default deny

This ordering is important: earlier matches can short-circuit later stages.

### 4.1 Traceability

Every stage appends an `ExplainTraceStep`.
Response traces are deterministic and include:

- `step`
- `outcome`
- `detail`
- `policy_id`

This is the core debugging feature for production support.

### 4.2 Condition evaluation

`ConditionEvaluator` implements handlers such as:

- `handle_role`
- `handle_max_amount`
- `handle_owner_only`
- `handle_time_range`
- `handle_geo_match`
- `handle_has_relation`

Unknown condition keys fail safely (`unknown condition: <key>`).

## 5) Simulation and impact analysis internals

### 5.1 Policy simulation

File: `keynetra/services/policy_simulator.py`

`simulate_policy_change(...)`:

1. Builds "before" decision via `AuthorizationService`
2. Parses proposed DSL with `dsl_to_policy`
3. Appends changed policy to current policy list
4. Builds temporary engine and computes "after" decision

Output: `SimulationResult(decision_before, decision_after)`

### 5.2 Impact analysis

File: `keynetra/services/impact_analysis.py`

`analyze_policy_change(...)`:

1. Loads current policies
2. Builds `before_engine` and `after_engine`
3. Iterates users and candidate resources
4. Compares before/after decision for target action
5. Returns `gained_access` and `lost_access`

Use this to estimate blast radius before deploying policy updates.

## 6) Caching and consistency details

Cache adapters used by service layer:

- Policy cache
- Relationship cache
- Decision cache
- ACL/access index caches

Consistency knobs in access APIs:

- `consistency: eventual` (default; uses decision cache)
- `consistency: fully_consistent` (bypasses decision cache)
- optional `revision` token for stronger control

## 7) Example: full request lifecycle

Request:

```json
{
  "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
  "action": "approve_payment",
  "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000},
  "context": {"department": "finance"}
}
```

Potential stage path:

- Direct permission stage matches `approve_payment`
- Engine returns allow with `policy_id=rbac:permissions`
- Service wraps response + revision + request metadata

## 8) Integration checklist

Before integrating in production:

1. Use `/check-access-batch` where N checks happen per request
2. Log `decision`, `reason`, `policy_id`, `revision`
3. Add policy simulation in CI review for policy changes
4. Add impact analysis for sensitive policy operations
5. Keep deny-by-default and least-privilege policies

## 9) Source map (quick links)

- API app bootstrap: `keynetra/api/main.py`
- Access routes: `keynetra/api/routes/access.py`
- Simulation routes: `keynetra/api/routes/simulation.py`
- Service orchestrator: `keynetra/services/authorization.py`
- Engine core: `keynetra/engine/keynetra_engine.py`
- Policy simulator: `keynetra/services/policy_simulator.py`
- Impact analysis: `keynetra/services/impact_analysis.py`
- CLI: `keynetra/cli.py`
