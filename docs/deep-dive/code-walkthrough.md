# Code Walkthrough (Line-by-Line Concepts)

This guide explains key classes and methods with implementation context.

## A) `keynetra/api/routes/access.py`

### `check_access(...)`

What it does:

1. Accepts validated `AccessRequest`
2. Calls `AuthorizationService.authorize(...)`
3. Converts service output to API schema (`AccessDecisionResponse`)
4. Returns standardized success envelope

Why this design:

- Route layer is transport-focused (HTTP validation/serialization)
- Business logic stays in service/engine layers

### `check_access_batch(...)`

What it does:

- Maps `BatchAccessRequest.items` into service input
- Returns per-item allow/deny results with revision

### `simulate(...)`

What it does:

- Calls `service.simulate(...)`
- Returns diagnostic fields like `failed_conditions`

## B) `keynetra/services/authorization.py`

### `AuthorizationService.__init__(...)`

Dependency injection of:

- repositories (tenants, policies, users, relationships, audit, ACL, model)
- caches (policy, relationship, decision, ACL, access index)
- settings (timeouts, resilience mode, etc.)

Benefit:

- easy testing with fake repositories/caches
- clear boundary between domain logic and storage

### `authorize(...)`

Notable behavior:

- Builds fallback input early for resilience path
- Uses decision cache unless `fully_consistent`
- Writes audit after decision
- Returns stable response even when backend fails (via fallback behavior)

### `_build_authorization_input(...)`

Adds optional data into `AuthorizationInput`:

- `acl_entries`
- `access_index_entries`
- `permission_graph`

This allows engine to evaluate multiple models in one run.

## C) `keynetra/engine/keynetra_engine.py`

### `AuthorizationInput`

Everything required for deterministic decision is explicit in this object.
No hidden external calls happen in the engine.

### `PolicyDefinition`

Normalized policy object with:

- `action`
- `effect`
- `conditions`
- `priority`
- `policy_id`

### `KeyNetraEngine.decide(...)`

Supports two call styles:

- new style: pass `AuthorizationInput`
- legacy style: `decide(user, action, resource)`

### `_decide_structured(...)`

This is the decision pipeline and the most important method to understand.
It appends trace steps for each stage and exits on first decisive stage.

## D) `keynetra/services/policy_simulator.py`

### `simulate_policy_change(...)`

- Computes before decision from current state
- Parses policy DSL (`dsl_to_policy`)
- Evaluates after decision in temporary engine
- Returns both decisions for direct comparison

## E) `keynetra/services/impact_analysis.py`

### `analyze_policy_change(...)`

- Compares before/after engines across user-resource candidates
- Reports changed user sets:
  - `gained_access`
  - `lost_access`

Interpretation tip:

- Large changed sets mean high blast radius; review carefully.

## F) `keynetra/cli.py`

Commands to map with API features:

- `check` -> `/check-access`
- `simulate` -> `/simulate-policy`
- `impact` -> `/impact-analysis`
- `test-policy` -> policy regression tests
- `compile-policies` -> policy compile/validation summary

Use CLI for reproducible scripts and CI jobs.
