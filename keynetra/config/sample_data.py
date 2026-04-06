from __future__ import annotations

import json
from typing import Any

SAMPLE_TENANT_KEY = "default"

SAMPLE_USER = {
    "id": 1,
    "external_id": "sample-manager",
}

SAMPLE_ROLE = {
    "name": "manager",
}

SAMPLE_PERMISSIONS = [
    {"action": "approve_payment"},
    {"action": "view_project"},
]

SAMPLE_RELATIONSHIPS = [
    {
        "subject_type": "user",
        "subject_id": "1",
        "relation": "member_of",
        "object_type": "team",
        "object_id": "engineering",
    }
]

SAMPLE_POLICY_DEFINITIONS = [
    {
        "policy_key": "approve-manager",
        "action": "approve_payment",
        "effect": "allow",
        "priority": 10,
        "conditions": {"role": "manager", "max_amount": 100000},
    },
    {
        "policy_key": "view-owner",
        "action": "view_project",
        "effect": "allow",
        "priority": 10,
        "conditions": {"owner_only": True},
    },
]

DEFAULT_POLICIES = [
    {
        "action": item["action"],
        "effect": item["effect"],
        "conditions": dict(item["conditions"]),
        "priority": item["priority"],
    }
    for item in SAMPLE_POLICY_DEFINITIONS
]


def sample_bootstrap_document() -> dict[str, Any]:
    return {
        "env": {
            "KEYNETRA_ENV": "development",
            "KEYNETRA_DEBUG": "true",
            "KEYNETRA_DATABASE_URL": "sqlite+pysqlite:///./keynetra.db",
            "KEYNETRA_REDIS_URL": "redis://localhost:6379/0",
            "KEYNETRA_API_KEYS": "devkey",
            "KEYNETRA_JWT_SECRET": "change-me",
            "KEYNETRA_JWT_ALGORITHM": "HS256",
            "KEYNETRA_CORS_ALLOW_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173",
            "KEYNETRA_CORS_ALLOW_CREDENTIALS": "true",
            "KEYNETRA_CORS_ALLOW_METHODS": "*",
            "KEYNETRA_CORS_ALLOW_HEADERS": "*",
            "KEYNETRA_POLICIES_JSON": json.dumps(DEFAULT_POLICIES, separators=(",", ":")),
            "KEYNETRA_POLICIES_CACHE_TTL_SECONDS": "5",
            "KEYNETRA_DECISION_CACHE_TTL_SECONDS": "5",
            "KEYNETRA_SERVICE_TIMEOUT_SECONDS": "2.0",
            "KEYNETRA_CRITICAL_RETRY_ATTEMPTS": "3",
            "KEYNETRA_RESILIENCE_MODE": "fail_closed",
            "KEYNETRA_RESILIENCE_FALLBACK_BEHAVIOR": "static",
            "KEYNETRA_RATE_LIMIT_PER_MINUTE": "60",
            "KEYNETRA_RATE_LIMIT_BURST": "60",
            "KEYNETRA_RATE_LIMIT_WINDOW_SECONDS": "60",
            "KEYNETRA_OTEL_ENABLED": "false",
            "KEYNETRA_SERVICE_MODE": "all",
            "KEYNETRA_POLICY_EVENTS_CHANNEL": "keynetra:policy_events",
        },
        "sample": {
            "tenant_key": SAMPLE_TENANT_KEY,
            "user": SAMPLE_USER,
            "role": SAMPLE_ROLE,
            "permissions": SAMPLE_PERMISSIONS,
            "relationships": SAMPLE_RELATIONSHIPS,
            "policies": SAMPLE_POLICY_DEFINITIONS,
        },
        "commands": {
            "seed": "PYTHONPATH=core python -m keynetra.cli seed-data --reset",
            "start": "PYTHONPATH=core python -m keynetra.cli start --host 0.0.0.0 --port 8000",
        },
    }
