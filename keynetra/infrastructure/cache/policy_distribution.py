from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from keynetra.config.redis_client import get_redis
from keynetra.config.settings import Settings
from keynetra.infrastructure.logging import log_event
from keynetra.services.interfaces import PolicyEventPublisher

_logger = logging.getLogger("keynetra.policy_distribution")


@dataclass(frozen=True)
class PolicyUpdateEvent:
    tenant_key: str
    policy_version: int

    def to_json(self) -> str:
        return json.dumps({"tenant_key": self.tenant_key, "policy_version": self.policy_version})


def publish_policy_update(settings: Settings, event: PolicyUpdateEvent) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.publish(settings.policy_events_channel, event.to_json())
    except (ConnectionError, OSError, RuntimeError, ValueError) as exc:
        log_event(
            _logger,
            event="policy_distribution_publish_failed",
            tenant_key=event.tenant_key,
            policy_version=event.policy_version,
            reason=repr(exc),
        )
        return


class RedisPolicyEventPublisher(PolicyEventPublisher):
    """Publish policy update notifications to Redis when available."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def publish_policy_update(self, *, tenant_key: str, policy_version: int) -> None:
        publish_policy_update(
            self._settings,
            PolicyUpdateEvent(tenant_key=tenant_key, policy_version=policy_version),
        )
