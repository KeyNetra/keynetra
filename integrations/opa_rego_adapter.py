"""OPA/Rego policy adapter with bidirectional translation.

Translates between KeyNetra's YAML/JSON policy definitions and
Open Policy Agent's Rego policy language. Supports import, export,
validation, and evaluation delegation to an external OPA server.
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Literal

from integrations.interfaces import PolicyAdapter


_REGO_COMMENT = re.compile(r"#.*$", re.MULTILINE)
_REGO_PACKAGE = re.compile(r"package\s+(\S+)")
_REGO_RULE = re.compile(
    r"(?:#\s*keynetra_id:\s*(\S+))?\s*"  # optional policy_id comment
    r"(?:#\s*keynetra_priority:\s*(\d+))?\s*"  # optional priority comment
    r"(?:#\s*keynetra_action:\s*(\S+))?\s*"  # optional action hint
    r"(deny|allow)\s*\[",
    re.MULTILINE,
)
_REGO_CONDITION = re.compile(r"(?:#\s*keynetra_(\w+):\s*(.+))", re.MULTILINE)


@dataclass
class RegoParseError(Exception):
    """Raised when Rego parsing fails."""
    message: str
    rego_snippet: str = ""


@dataclass(frozen=True)
class RegoPolicy:
    """A single policy rule parsed from Rego."""
    effect: Literal["allow", "deny"]
    action: str
    conditions: dict[str, Any]
    priority: int
    policy_id: str | None


@dataclass(frozen=True)
class RegoEvaluationResult:
    """Result of evaluating a Rego policy against an input."""
    allowed: bool
    decision: Literal["allow", "deny"]
    matched_policies: list[str]
    explain: list[dict[str, Any]]


def _normalize_action(action: str) -> str:
    """Normalize action for use in rule names."""
    return action.replace("-", "_").replace(".", "_").replace(":", "_")


def _denormalize_action(action: str) -> str:
    """Reverse normalization."""
    return action.replace("_", "-")


def _sanitize_identifier(value: str) -> str:
    """Sanitize a string for use as a Rego identifier."""
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(value))
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized or "_"


def _condition_to_rego(conditions: dict[str, Any], action: str, priority: int, policy_id: str | None) -> str:
    """Convert KeyNetra conditions to Rego rule body."""
    parts: list[str] = []
    comments: list[str] = []

    if policy_id:
        comments.append(f"    # keynetra_id: {policy_id}")
    comments.append(f"    # keynetra_priority: {priority}")
    comments.append(f"    # keynetra_action: {action}")

    # Role condition
    role = conditions.get("role")
    if role:
        parts.append(f"    input.user.role == \"{role}\"")
    elif "roles" in conditions:
        roles = conditions["roles"]
        if isinstance(roles, list) and roles:
            role_checks = " | ".join(f"input.user.roles[_] == \"{r}\"" for r in roles)
            parts.append(f"    {role_checks}")
        elif isinstance(roles, str):
            parts.append(f"    input.user.roles[_] == \"{roles}\"")

    # Resource type condition
    resource_type = conditions.get("resource_type") or conditions.get("type")
    if resource_type:
        parts.append(f"    input.resource.resource_type == \"{resource_type}\"")

    # Owner-only condition
    owner_only = conditions.get("owner_only")
    if owner_only:
        parts.append("    input.resource.owner_id == input.user.id")

    # Relation / has_relation condition
    relation = conditions.get("relation") or conditions.get("has_relation", {}).get("relation")
    if relation:
        object_type = conditions.get("object_type", conditions.get("has_relation", {}).get("object_type", ""))
        object_id_field = conditions.get("has_relation", {}).get("object_id_from_resource", "resource_id")
        parts.append(f"    some i")
        parts.append(f"    input.user.relations[i].relation == \"{relation}\"")
        if object_type:
            parts.append(f"    input.user.relations[i].object_type == \"{object_type}\"")
        if object_id_field:
            parts.append(f"    input.user.relations[i].object_id == input.resource.{object_id_field}")

    # Geo match
    geo_match = conditions.get("geo_match")
    if isinstance(geo_match, dict):
        user_field = geo_match.get("user_field", "country")
        resource_field = geo_match.get("resource_field", "country")
        parts.append(f"    input.user.{_sanitize_identifier(user_field)} == input.resource.{_sanitize_identifier(resource_field)}")

    # Time range
    time_range = conditions.get("time_range")
    if isinstance(time_range, dict):
        start = time_range.get("start", "00:00")
        end = time_range.get("end", "23:59")
        parts.append(f"    time_compare(input.context.current_time, \"{start}\", \"{end}\")")

    # Max amount
    max_amount = conditions.get("max_amount")
    if max_amount is not None:
        parts.append(f"    input.resource.amount <= {float(max_amount)}")

    # Same tenant
    if conditions.get("same_tenant"):
        parts.append("    input.user.tenant == input.resource.tenant")

    # Resource attribute condition
    resource_attr = conditions.get("resource_attr")
    if isinstance(resource_attr, dict):
        for attr_name, attr_value in resource_attr.items():
            if isinstance(attr_value, str):
                parts.append(f"    input.resource.{_sanitize_identifier(attr_name)} == \"{attr_value}\"")
            elif isinstance(attr_value, (int, float, bool)):
                parts.append(f"    input.resource.{_sanitize_identifier(attr_name)} == {json.dumps(attr_value)}")

    # Custom conditions
    custom = conditions.get("custom", {})
    if isinstance(custom, dict):
        for key, value in custom.items():
            if isinstance(value, str):
                parts.append(f"    input.resource.{_sanitize_identifier(key)} == \"{value}\"")
            elif isinstance(value, bool):
                if value:
                    parts.append(f"    input.resource.{_sanitize_identifier(key)}")
                else:
                    parts.append(f"    not input.resource.{_sanitize_identifier(key)}")

    comments_text = "\n".join(comments)
    if parts:
        return f"{comments_text}\n" + "\n".join(parts)
    # If no conditions, match everything (default allow/deny for action)
    return f"{comments_text}\n    true"


def _parse_rego_conditions(rego_text: str, start_idx: int) -> dict[str, Any]:
    """Parse conditions from a Rego rule body section."""
    conditions: dict[str, Any] = {}
    lines = rego_text[start_idx:].split("\n")

    # Extract metadata from comments
    for line in lines[:10]:  # check first 10 lines for metadata
        stripped = line.strip()

        # Check for resource type condition in rule body
        resource_match = re.search(r'input\.resource\.resource_type\s*==\s*"([^"]+)"', stripped)
        if resource_match:
            conditions["resource_type"] = resource_match.group(1)

        role_match = re.search(r"input\.user\.role\s*==\s*\"([^\"]+)\"", stripped)
        if role_match:
            conditions["role"] = role_match.group(1)

        owner_match = re.search(r"input\.resource\.owner_id\s*==\s*input\.user\.id", stripped)
        if owner_match:
            conditions["owner_only"] = True

        relation_match = re.search(r'input\.user\.relations\[.*\]\.relation\s*==\s*"([^"]+)"', stripped)
        if relation_match:
            conditions["relation"] = relation_match.group(1)

        max_amount_match = re.search(r"input\.resource\.amount\s*<=\s*([\d.]+)", stripped)
        if max_amount_match:
            conditions["max_amount"] = float(max_amount_match.group(1))

        same_tenant_match = re.search(r"input\.user\.tenant\s*==\s*input\.resource\.tenant", stripped)
        if same_tenant_match:
            conditions["same_tenant"] = True

    return conditions


def _extract_metadata_from_rego_lines(lines: list[str]) -> tuple[str | None, int | None, str | None]:
    """Extract policy_id, priority, and action from Rego comment metadata."""
    policy_id: str | None = None
    priority: int | None = None
    action: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# keynetra_id:"):
            policy_id = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("# keynetra_priority:"):
            try:
                priority = int(stripped.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                pass
        elif stripped.startswith("# keynetra_action:"):
            action = stripped.split(":", 1)[1].strip()

    return policy_id, priority, action


OPA_DEFAULT_PACKAGE = "keynetra.authz"


class OPARegoPolicyAdapter(PolicyAdapter):
    """Bidirectional OPA/Rego policy adapter.

    Converts KeyNetra policy definitions to Rego and back.
    Supports import from Rego strings and export to Rego,
    optional HTTP-based evaluation against an external OPA server,
    and standalone in-process evaluation.
    """

    def __init__(
        self,
        rego: str = "",
        *,
        opa_endpoint: str | None = None,
        opa_bearer_token: str | None = None,
        package_name: str = OPA_DEFAULT_PACKAGE,
    ) -> None:
        self._rego = rego
        self._opa_endpoint = opa_endpoint
        self._opa_bearer_token = opa_bearer_token
        self._package_name = package_name
        self._parsed_policies: list[RegoPolicy] = []

    def import_policies(self, payload: str) -> int:
        """Import Rego policy text.

        Supports both raw Rego and JSON-encoded KeyNetra policy definitions.
        If payload is a JSON array of policy objects, converts them to Rego.
        Otherwise treats as raw Rego.
        """
        # Try to detect if this is a JSON policy array from KeyNetra
        stripped = payload.strip()
        if stripped.startswith("[") or stripped.startswith("{\"policies"):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    policies = parsed
                elif isinstance(parsed, dict) and "policies" in parsed:
                    policies = parsed["policies"]
                else:
                    policies = [parsed]
                self._rego = self._policies_to_rego(policies, package=self._package_name)
                self._parsed_policies = []
                return len(policies)
            except (json.JSONDecodeError, TypeError):
                pass

        # Treat as raw Rego
        self._rego = stripped
        self._parsed_policies = self._parse_rego_policies(self._rego)
        return len(self._parsed_policies) if self._parsed_policies else 1

    def export_policies(self) -> str:
        """Export current policies as Rego text."""
        return self._rego or ""

    def to_keynetra_policies(self) -> list[dict[str, Any]]:
        """Convert loaded Rego policies back to KeyNetra policy dicts."""
        if not self._parsed_policies:
            self._parsed_policies = self._parse_rego_policies(self._rego)
        result: list[dict[str, Any]] = []
        for policy in self._parsed_policies:
            entry: dict[str, Any] = {
                "action": policy.action,
                "effect": policy.effect,
                "priority": policy.priority,
            }
            if policy.policy_id:
                entry["policy_id"] = policy.policy_id
            entry["conditions"] = policy.conditions
            result.append(entry)
        return result

    def import_from_keynetra(self, policies: list[dict[str, Any]], *, package: str | None = None) -> int:
        """Import policies from KeyNetra format, converting to Rego."""
        self._rego = self._policies_to_rego(policies, package=package or self._package_name)
        self._parsed_policies = [
            RegoPolicy(
                effect=p.get("effect", "deny"),
                action=p.get("action", ""),
                conditions=p.get("conditions", {}),
                priority=p.get("priority", 100),
                policy_id=p.get("policy_id"),
            )
            for p in policies
        ]
        return len(policies)

    def validate(self) -> list[str]:
        """Validate the loaded Rego for basic correctness.

        Returns a list of validation errors, empty if valid.
        """
        errors: list[str] = []
        if not self._rego.strip():
            errors.append("empty rego")
            return errors

        lines = self._rego.strip().split("\n")

        # Check package declaration exists
        package_found = any(line.strip().startswith("package ") for line in lines)
        if not package_found:
            errors.append("missing package declaration")

        # Check rule declarations exist
        rule_found = any(
            line.strip().startswith("allow") or line.strip().startswith("deny")
            for line in lines
        )
        if not rule_found:
            errors.append("no allow/deny rules found (must have at least one rule)")
        else:
            # Parse rules to validate structure
            try:
                self._parsed_policies = self._parse_rego_policies(self._rego)
            except RegoParseError as e:
                errors.append(str(e))

        return errors

    def _policies_to_rego(self, policies: list[dict[str, Any]], *, package: str) -> str:
        """Convert KeyNetra policy definitions to Rego source code."""
        lines: list[str] = [
            f"package {package}",
            "",
            "import future.keywords.if",
            "import future.keywords.in",
            "",
            "default allow := false",
            "default deny := false",
            "",
            "# Time comparison helper",
            "time_compare(time_in, start, end) if {",
            "    t := split(time_in, \":\");",
            "    s := split(start, \":\");",
            "    e := split(end, \":\");",
            "    t_h := to_number(t[0]); t_m := to_number(t[1]);",
            "    s_h := to_number(s[0]); s_m := to_number(s[1]);",
            "    e_h := to_number(e[0]); e_m := to_number(e[1]);",
            "    t_total := t_h * 60 + t_m;",
            "    s_total := s_h * 60 + s_m;",
            "    e_total := e_h * 60 + e_m;",
            "    s_total <= t_total; t_total <= e_total;",
            "}",
            "",
        ]

        allow_rules: list[str] = []
        deny_rules: list[str] = []

        for i, policy in enumerate(policies):
            effect = policy.get("effect", "deny")
            action = policy.get("action", "")
            conditions = policy.get("conditions", {})
            priority = policy.get("priority", 100)
            policy_id = policy.get("policy_id")
            rule_name = f"rule_{_sanitize_identifier(action)}_{i}"

            condition_rego = _condition_to_rego(conditions, action, priority, policy_id)

            if effect == "allow":
                allow_rules.append(f"allow if {{\n{condition_rego}\n}}")
            else:
                deny_rules.append(f"deny if {{\n{condition_rego}\n}}")

        if not allow_rules:
            lines.append("# No allow rules defined; all access defaults to deny by default")
        else:
            lines.append("# Allow rules:")
            lines.append("")
            for rule in allow_rules:
                lines.append(rule)
                lines.append("")

        if deny_rules:
            lines.append("# Deny rules:")
            lines.append("")
            for rule in deny_rules:
                lines.append(rule)
                lines.append("")

        return "\n".join(lines)

    def _parse_rego_policies(self, rego: str) -> list[RegoPolicy]:
        """Parse Rego source into RegoPolicy objects."""
        if not rego.strip():
            return []

        policies: list[RegoPolicy] = []
        lines = rego.split("\n")

        # Strip comments for rule detection but keep for metadata extraction
        cleaned = _REGO_COMMENT.sub("", rego)

        # Find all rule blocks
        allow_blocks = _find_rule_blocks(rego, "allow")
        deny_blocks = _find_rule_blocks(rego, "deny")

        for block in allow_blocks:
            block_lines = rego[block["start"]:block["end"]].split("\n")
            pid, priority, action = _extract_metadata_from_rego_lines(block_lines)
            conditions = _parse_rego_conditions(rego, block["body_start"])
            if action is None:
                action = conditions.get("action") or conditions.get("resource_type", "*")
            policies.append(RegoPolicy(
                effect="allow",
                action=action,
                conditions=conditions,
                priority=priority or 100,
                policy_id=pid,
            ))

        for block in deny_blocks:
            block_lines = rego[block["start"]:block["end"]].split("\n")
            pid, priority, action = _extract_metadata_from_rego_lines(block_lines)
            conditions = _parse_rego_conditions(rego, block["body_start"])
            if action is None:
                action = conditions.get("action") or conditions.get("resource_type", "*")
            policies.append(RegoPolicy(
                effect="deny",
                action=action,
                conditions=conditions,
                priority=priority or 100,
                policy_id=pid,
            ))

        return policies

    def evaluate_locally(self, input_data: dict[str, Any]) -> RegoEvaluationResult:
        """Evaluate access locally using simplified rule matching.

        This is a best-effort local evaluation that does NOT use the full OPA
        Rego engine. For production evaluation, use evaluate_via_opa() or
        delegate to a real OPA server.

        This method matches KeyNetra conditions against the input to determine
        if a rule would allow or deny the request.
        """
        if not self._parsed_policies:
            self._parsed_policies = self._parse_rego_policies(self._rego)

        matched: list[str] = []
        # Check deny rules first (deny takes precedence)
        for policy in self._parsed_policies:
            if policy.effect == "deny":
                if self._match_conditions_locally(policy.conditions, input_data, policy_action=policy.action):
                    matched.append(policy.policy_id or f"deny:{policy.action}")
                    return RegoEvaluationResult(
                        allowed=False,
                        decision="deny",
                        matched_policies=matched,
                        explain=[{"rule": str(policy), "effect": "deny"}],
                    )

        # Check allow rules
        for policy in self._parsed_policies:
            if policy.effect == "allow":
                if self._match_conditions_locally(policy.conditions, input_data, policy_action=policy.action):
                    matched.append(policy.policy_id or f"allow:{policy.action}")
                    return RegoEvaluationResult(
                        allowed=True,
                        decision="allow",
                        matched_policies=matched,
                        explain=[{"rule": str(policy), "effect": "allow"}],
                    )

        # Default deny
        return RegoEvaluationResult(
            allowed=False,
            decision="deny",
            matched_policies=[],
            explain=[{"effect": "deny", "reason": "no matching rules"}],
        )

    def _match_conditions_locally(self, conditions: dict[str, Any], input_data: dict[str, Any], policy_action: str | None = None) -> bool:
        """Check if conditions match the input. Simplified engine-matching.

        Args:
            conditions: The conditions dict from the policy
            input_data: The full input dict with user, resource, action, context
            policy_action: The action this policy is for. If provided, the input
                          must match this action to be considered matching.
        """
        user = input_data.get("user", {})
        resource = input_data.get("resource", {})
        context = input_data.get("context", {})
        input_action = input_data.get("action")

        # Check action match - if policy has an action and input has an action,
        # they must match (or policy action must be "*")
        if policy_action and input_action:
            if policy_action != "*" and policy_action != input_action:
                return False

        # Role check
        role = conditions.get("role")
        if role:
            user_role = user.get("role")
            if user_role != role:
                return False

        # Roles check (list)
        roles = conditions.get("roles")
        if isinstance(roles, list):
            user_roles = user.get("roles", [user.get("role")])
            if not any(r in user_roles for r in roles):
                return False

        # Resource type
        resource_type = conditions.get("resource_type")
        if resource_type:
            actual_type = resource.get("resource_type") or resource.get("type")
            if actual_type != resource_type:
                return False

        # Owner only
        if conditions.get("owner_only"):
            if resource.get("owner_id") != user.get("id"):
                return False

        # Relation check
        relation = conditions.get("relation")
        if relation:
            user_relations = user.get("relations", [])
            if not isinstance(user_relations, list):
                return False
            relation_matched = False
            for rel in user_relations:
                if isinstance(rel, dict):
                    if rel.get("relation") == relation:
                        resource_type_check = conditions.get("object_type", resource.get("resource_type"))
                        if not resource_type_check or rel.get("object_type") == resource_type_check:
                            relation_matched = True
                            break
            if not relation_matched:
                return False

        # Same tenant
        if conditions.get("same_tenant"):
            if user.get("tenant") != resource.get("tenant"):
                return False

        # Max amount
        max_amount = conditions.get("max_amount")
        if max_amount is not None:
            try:
                if float(resource.get("amount", 0)) > float(max_amount):
                    return False
            except (TypeError, ValueError):
                pass

        return True

    def evaluate_via_opa(self, input_data: dict[str, Any], *, timeout: int = 10) -> RegoEvaluationResult:
        """Evaluate against an external OPA server via its REST API.

        Requires opa_endpoint to be configured.
        """
        if not self._opa_endpoint:
            raise RuntimeError(
                "OPA endpoint not configured. Set opa_endpoint in constructor "
                "or use evaluate_locally() for simplified evaluation."
            )

        url = f"{self._opa_endpoint.rstrip('/')}/v1/data/{self._package_name.replace('.', '/')}"
        body = json.dumps({"input": input_data}).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )
        if self._opa_bearer_token:
            req.add_header("Authorization", f"Bearer {self._opa_bearer_token}")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
            raise RuntimeError(f"OPA evaluation failed: {e}") from e

        decision = result.get("result", {})
        allow = decision.get("allow", False)
        deny = decision.get("deny", False)

        return RegoEvaluationResult(
            allowed=allow and not deny,
            decision="deny" if deny else ("allow" if allow else "deny"),
            matched_policies=decision.get("matched_policies", []),
            explain=decision.get("explain", []),
        )

    def to_keynetra_policy_yaml(self) -> str:
        """Export policies as KeyNetra YAML-style policy definition."""
        policies = self.to_keynetra_policies()
        lines: list[str] = ["policies:"]
        for p in policies:
            lines.append(f"  - action: {p['action']}")
            lines.append(f"    effect: {p['effect']}")
            lines.append(f"    priority: {p['priority']}")
            if p.get("policy_id"):
                lines.append(f"    policy_id: {p['policy_id']}")
            if p.get("conditions"):
                lines.append("    conditions:")
                for key, value in p["conditions"].items():
                    if isinstance(value, dict):
                        lines.append(f"      {key}:")
                        for k, v in value.items():
                            lines.append(f"        {k}: {v}")
                    elif isinstance(value, list):
                        lines.append(f"      {key}:")
                        for v in value:
                            lines.append(f"        - {v}")
                    else:
                        lines.append(f"      {key}: {value}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        pkg = self._package_name
        rule_count = len(self._parsed_policies) if self._parsed_policies else 0
        return f"OPARegoPolicyAdapter(package={pkg}, rules={rule_count}, opa={'connected' if self._opa_endpoint else 'local'})"


def _find_rule_blocks(rego_text: str, rule_type: str) -> list[dict[str, Any]]:
    """Find rule blocks of a given type (allow/deny) in Rego text."""
    blocks: list[dict[str, Any]] = []
    pattern = re.compile(
        rf"^{rule_type}\s+if\s*{{" if rule_type in ("allow", "deny") else re.compile(rule_type),
        re.MULTILINE,
    )

    idx = 0
    while True:
        match = pattern.search(rego_text, idx)
        if not match:
            break

        start = match.start()
        body_start = match.end()

        # Find matching closing brace
        brace_count = 1
        pos = body_start
        while pos < len(rego_text) and brace_count > 0:
            if rego_text[pos] == "{":
                brace_count += 1
            elif rego_text[pos] == "}":
                brace_count -= 1
            pos += 1

        end = pos if brace_count == 0 else len(rego_text)

        blocks.append({
            "start": start,
            "body_start": body_start,
            "end": end,
        })
        idx = end

    return blocks