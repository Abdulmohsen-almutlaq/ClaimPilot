import httpx
import pytest
import respx

from app.tools import crm
from app.tools.circuit_breaker import CircuitBreaker, CircuitOpenError

CRM_BASE = "http://localhost:8001"


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _breaker(clock: _FakeClock) -> CircuitBreaker:
    return CircuitBreaker(failure_threshold=3, open_seconds=30, clock=clock)


def test_opens_after_threshold_consecutive_failures() -> None:
    clock = _FakeClock()
    breaker = _breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open
    breaker.record_failure()
    assert breaker.is_open
    with pytest.raises(CircuitOpenError):
        breaker.check()


def test_success_resets_consecutive_count() -> None:
    clock = _FakeClock()
    breaker = _breaker(clock)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open  # never reached 3 in a row


def test_closes_after_open_period_and_reopens_on_next_failure() -> None:
    clock = _FakeClock()
    breaker = _breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open

    clock.now += 31  # open period lapses -> half-open: calls allowed again
    assert not breaker.is_open
    breaker.check()

    # a single failed probe re-opens immediately (no need for 3 more failures)
    breaker.record_failure()
    assert breaker.is_open


def test_success_after_open_period_closes_fully() -> None:
    clock = _FakeClock()
    breaker = _breaker(clock)
    for _ in range(3):
        breaker.record_failure()
    clock.now += 31
    breaker.record_success()

    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open  # back to needing 3 consecutive failures


async def test_crm_breaker_short_circuits_after_repeated_5xx() -> None:
    crm.reset_breaker()
    with respx.mock(base_url=CRM_BASE) as mock:
        route = mock.get("/policies/POL-AUTO-001").mock(return_value=httpx.Response(503))

        for _ in range(3):
            with pytest.raises(crm.CRMUnavailableError):
                await crm.lookup_policy("POL-AUTO-001")
        assert route.call_count == 3

        # Breaker is now open: the next call is refused WITHOUT an HTTP request.
        with pytest.raises(CircuitOpenError):
            await crm.lookup_policy("POL-AUTO-001")
        assert route.call_count == 3


async def test_crm_404_counts_as_healthy_dependency() -> None:
    crm.reset_breaker()
    with respx.mock(base_url=CRM_BASE) as mock:
        mock.get("/policies/UNKNOWN").mock(return_value=httpx.Response(404))
        for _ in range(5):
            with pytest.raises(crm.CRMNotFoundError):
                await crm.lookup_policy("UNKNOWN")
    assert not crm.get_breaker().is_open
