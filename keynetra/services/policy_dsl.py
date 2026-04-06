from __future__ import annotations

import json
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - optional parser dependency
    yaml = None  # type: ignore[assignment]


def dsl_to_policy(dsl_text: str) -> dict[str, Any]:
    """
    Minimal DSL example:
      allow:
        action: read
        priority: 10
        policy_key: read_rule
        when:
          role: admin
          owner_only: true
    """
    data = (
        yaml.safe_load(dsl_text)
        if yaml is not None
        else json.loads(dsl_text)  # Allow JSON payloads when PyYAML is unavailable.
    )
    if not isinstance(data, dict) or not data:
        raise ValueError("invalid dsl")

    if "allow" in data:
        block = data["allow"]
        effect = "allow"
    elif "deny" in data:
        block = data["deny"]
        effect = "deny"
    else:
        raise ValueError("dsl must start with allow: or deny:")

    if not isinstance(block, dict):
        raise ValueError("invalid dsl block")

    action = block.get("action")
    if not isinstance(action, str) or not action:
        raise ValueError("missing action")

    when = block.get("when") or {}
    if when is None:
        when = {}
    if not isinstance(when, dict):
        raise ValueError("when must be an object")

    priority = int(block.get("priority", 100))
    policy_key = block.get("policy_key") or action

    return {
        "action": action,
        "effect": effect,
        "priority": priority,
        "conditions": dict(when) | {"policy_key": str(policy_key)},
    }
