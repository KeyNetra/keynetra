from __future__ import annotations

import os

import pytest

pytest.importorskip("redis")

import redis

from keynetra.engine.keynetra_engine import AuthorizationInput, PolicyDefinition
from keynetra.infrastructure.cache.access_index_cache import RedisBackedAccessIndexCache
from keynetra.infrastructure.cache.acl_cache import RedisBackedACLCache
from keynetra.infrastructure.cache.backends import build_cache_backend
from keynetra.infrastructure.cache.decision_cache import RedisBackedDecisionCache
from keynetra.infrastructure.cache.policy_cache import RedisBackedPolicyCache
from keynetra.infrastructure.cache.relationship_cache import RedisBackedRelationshipCache
from keynetra.services.interfaces import AccessIndexEntry, ACLRecord, CachedDecision, PolicyRecord


def _redis_url() -> str:
    return os.environ.get("KEYNETRA_REDIS_URL", "redis://localhost:6379/15")


def _redis_client() -> redis.Redis:
    client = redis.Redis.from_url(_redis_url(), decode_responses=True)
    try:
        client.ping()
    except Exception as exc:  # pragma: no cover - skipped in environments without Redis
        pytest.skip(f"redis integration test requires a reachable Redis server: {exc}")
    return client


def test_redis_multi_node_cache_invalidation_propagates_across_nodes() -> None:
    client_a = _redis_client()
    client_b = redis.Redis.from_url(_redis_url(), decode_responses=True)
    backend_a = build_cache_backend(client_a)
    backend_b = build_cache_backend(client_b)

    client_a.flushdb()

    policy_cache_a = RedisBackedPolicyCache(backend_a)
    policy_cache_b = RedisBackedPolicyCache(backend_b)
    decision_cache_a = RedisBackedDecisionCache(backend_a)
    decision_cache_b = RedisBackedDecisionCache(backend_b)
    acl_cache_a = RedisBackedACLCache(backend_a)
    acl_cache_b = RedisBackedACLCache(backend_b)
    access_index_cache_a = RedisBackedAccessIndexCache(backend_a)
    access_index_cache_b = RedisBackedAccessIndexCache(backend_b)
    relationship_cache_a = RedisBackedRelationshipCache(backend_a)
    relationship_cache_b = RedisBackedRelationshipCache(backend_b)

    policy_cache_a.set(
        "default",
        1,
        [
            PolicyRecord(
                id=1,
                definition=PolicyDefinition(
                    action="read",
                    effect="allow",
                    priority=1,
                    policy_id="policy:read",
                    conditions={},
                ),
            )
        ],
    )
    assert policy_cache_b.get("default", 1) is not None
    policy_cache_b.invalidate("default")
    assert policy_cache_a.get("default", 1) is None

    authorization_input = AuthorizationInput(
        user={"id": 1},
        resource={"resource_type": "doc", "resource_id": "doc-1"},
        action="read",
        tenant_key="default",
    )
    decision_key_before = decision_cache_a.make_key(
        tenant_key="default",
        policy_version=1,
        authorization_input=authorization_input,
        revision=1,
    )
    decision_cache_a.set(
        decision_key_before,
        CachedDecision(
            allowed=True,
            decision="allow",
            reason="cached",
            policy_id="policy:read",
        ),
        ttl_seconds=30,
    )
    assert decision_cache_b.get(decision_key_before) is not None
    decision_cache_b.bump_namespace("default")
    decision_key_after = decision_cache_a.make_key(
        tenant_key="default",
        policy_version=1,
        authorization_input=authorization_input,
        revision=1,
    )
    assert decision_key_after != decision_key_before
    assert decision_cache_a.get(decision_key_after) is None

    acl_cache_a.set(
        tenant_id=1,
        resource_type="doc",
        resource_id="doc-1",
        action="read",
        acl_entries=[
            ACLRecord(
                id=1,
                tenant_id=1,
                subject_type="user",
                subject_id="1",
                resource_type="doc",
                resource_id="doc-1",
                action="read",
                effect="allow",
            )
        ],
    )
    assert (
        acl_cache_b.get(tenant_id=1, resource_type="doc", resource_id="doc-1", action="read")
        is not None
    )
    acl_cache_b.invalidate(tenant_id=1, resource_type="doc", resource_id="doc-1")
    assert (
        acl_cache_a.get(tenant_id=1, resource_type="doc", resource_id="doc-1", action="read")
        is None
    )

    access_index_cache_a.set(
        tenant_id=1,
        resource_type="doc",
        resource_id="doc-1",
        action="read",
        entries=[
            AccessIndexEntry(
                resource_type="doc",
                resource_id="doc-1",
                action="read",
                allowed_subjects=("user:1",),
                source="acl",
                subject_type="user",
                subject_id="1",
                effect="allow",
                acl_id=1,
            )
        ],
    )
    assert (
        access_index_cache_b.get(
            tenant_id=1, resource_type="doc", resource_id="doc-1", action="read"
        )
        is not None
    )
    access_index_cache_b.invalidate(tenant_id=1, resource_type="doc", resource_id="doc-1")
    assert (
        access_index_cache_a.get(
            tenant_id=1, resource_type="doc", resource_id="doc-1", action="read"
        )
        is None
    )

    relationship_cache_a.set(
        tenant_id=1,
        subject_type="user",
        subject_id="1",
        relationships=[],
    )
    assert relationship_cache_b.get(tenant_id=1, subject_type="user", subject_id="1") is not None
    relationship_cache_b.invalidate(tenant_id=1, subject_type="user", subject_id="1")
    assert relationship_cache_a.get(tenant_id=1, subject_type="user", subject_id="1") is None
