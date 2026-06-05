from __future__ import annotations

import pybreaker
import pytest

from apps.ingestion.circuit import get_breaker


@pytest.fixture(autouse=True)
def clear_breaker_cache() -> None:
    get_breaker.cache_clear()


def _failing() -> None:
    raise RuntimeError("boom")


@pytest.mark.django_db
def test_breaker_opens_at_5th_consecutive_failure() -> None:
    """fail_max=5 means the 5th failure trips the breaker;
    call #5 itself raises CircuitBreakerError (chained from RuntimeError)."""
    breaker = get_breaker("test_source_a")
    breaker.close()

    for _ in range(4):
        with pytest.raises(RuntimeError):
            breaker.call(_failing)

    with pytest.raises(pybreaker.CircuitBreakerError):
        breaker.call(_failing)

    # And subsequent calls are also short-circuited.
    with pytest.raises(pybreaker.CircuitBreakerError):
        breaker.call(_failing)


@pytest.mark.django_db
def test_breaker_state_is_per_source() -> None:
    """One source's breaker opening must not affect another's."""
    a = get_breaker("test_source_b")
    b = get_breaker("test_source_c")
    a.close()
    b.close()

    # Trip A
    for _ in range(4):
        with pytest.raises(RuntimeError):
            a.call(_failing)
    with pytest.raises(pybreaker.CircuitBreakerError):
        a.call(_failing)

    # B is unaffected — call propagates the underlying RuntimeError, failure count = 1.
    with pytest.raises(RuntimeError):
        b.call(_failing)
