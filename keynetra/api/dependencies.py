from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings, get_settings
from keynetra.infrastructure.cache.access_index_cache import build_access_index_cache
from keynetra.infrastructure.cache.acl_cache import build_acl_cache
from keynetra.infrastructure.cache.decision_cache import build_decision_cache
from keynetra.infrastructure.cache.policy_cache import build_policy_cache
from keynetra.infrastructure.cache.policy_distribution import RedisPolicyEventPublisher
from keynetra.infrastructure.cache.relationship_cache import build_relationship_cache
from keynetra.infrastructure.repositories.acl import SqlACLRepository
from keynetra.infrastructure.repositories.audit import SqlAuditRepository
from keynetra.infrastructure.repositories.auth_models import SqlAuthModelRepository
from keynetra.infrastructure.repositories.policies import SqlPolicyRepository
from keynetra.infrastructure.repositories.relationships import SqlRelationshipRepository
from keynetra.infrastructure.repositories.tenants import SqlTenantRepository
from keynetra.infrastructure.repositories.users import SqlUserRepository
from keynetra.infrastructure.storage.session import get_db
from keynetra.services.access_indexer import AccessIndexer
from keynetra.services.authorization import AuthorizationService
from keynetra.services.policies import PolicyService
from keynetra.services.policy_lint import PolicyLintService
from keynetra.services.relationships import RelationshipService


@dataclass(frozen=True)
class ServiceContainer:
    settings: Settings
    tenant_repo: SqlTenantRepository
    policy_repo: SqlPolicyRepository
    user_repo: SqlUserRepository
    relationship_repo: SqlRelationshipRepository
    acl_repo: SqlACLRepository
    audit_repo: SqlAuditRepository
    auth_model_repo: SqlAuthModelRepository
    authorization_service: AuthorizationService
    policy_service: PolicyService
    policy_lint_service: PolicyLintService
    relationship_service: RelationshipService
    access_indexer: AccessIndexer


def build_services(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ServiceContainer:
    redis_client = get_redis()
    tenant_repo = SqlTenantRepository(db)
    policy_repo = SqlPolicyRepository(db)
    relationship_repo = SqlRelationshipRepository(db)
    acl_repo = SqlACLRepository(db)
    access_indexer = AccessIndexer(
        acl_repository=acl_repo,
        acl_cache=build_acl_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
        relationships=relationship_repo,
    )
    request_id = getattr(request.state, "request_id", None)
    authorization_service = AuthorizationService(
        settings=settings,
        tenants=tenant_repo,
        policies=policy_repo,
        users=SqlUserRepository(db),
        relationships=relationship_repo,
        audit=SqlAuditRepository(db),
        policy_cache=build_policy_cache(redis_client),
        relationship_cache=build_relationship_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        acl_repository=acl_repo,
        acl_cache=build_acl_cache(redis_client),
        access_index_cache=build_access_index_cache(redis_client),
        auth_model_repository=SqlAuthModelRepository(db),
        request_id=request_id,
    )
    policy_service = PolicyService(
        tenants=tenant_repo,
        policies=policy_repo,
        policy_cache=build_policy_cache(redis_client),
        decision_cache=build_decision_cache(redis_client),
        publisher=RedisPolicyEventPublisher(settings),
    )
    return ServiceContainer(
        settings=settings,
        tenant_repo=tenant_repo,
        policy_repo=policy_repo,
        user_repo=SqlUserRepository(db),
        relationship_repo=relationship_repo,
        acl_repo=acl_repo,
        audit_repo=SqlAuditRepository(db),
        auth_model_repo=SqlAuthModelRepository(db),
        authorization_service=authorization_service,
        policy_service=policy_service,
        policy_lint_service=PolicyLintService(session=db, policies=policy_repo),
        relationship_service=RelationshipService(
            tenants=tenant_repo,
            relationships=relationship_repo,
            relationship_cache=build_relationship_cache(redis_client),
            decision_cache=build_decision_cache(redis_client),
            access_index_cache=build_access_index_cache(redis_client),
        ),
        access_indexer=access_indexer,
    )
