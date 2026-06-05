from __future__ import annotations

from functools import cache

import pybreaker
import redis
from django.conf import settings


@cache
def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)


@cache
def get_breaker(source_slug: str) -> pybreaker.CircuitBreaker:
    """Return a per-source circuit breaker backed by Redis (shared across workers)."""
    storage = pybreaker.CircuitRedisStorage(
        state=pybreaker.STATE_CLOSED,
        redis_object=_redis_client(),
        namespace=f"scm:breaker:{source_slug}",
    )
    return pybreaker.CircuitBreaker(
        fail_max=5,
        reset_timeout=300,
        state_storage=storage,
        name=source_slug,
    )
