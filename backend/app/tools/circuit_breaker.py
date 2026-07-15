import time
from collections.abc import Callable


class CircuitOpenError(Exception):
    """The protected dependency is presumed down; the call was refused without
    being attempted."""


class CircuitBreaker:
    """Consecutive-failure circuit breaker. After `failure_threshold` failures
    in a row the circuit opens for `open_seconds`: calls are refused instantly
    instead of burning a timeout each. When the open period lapses the breaker
    is effectively half-open — the failure count is NOT reset, so a single
    failed probe re-opens it immediately, while one success closes it fully.

    The clock is injected so tests control time instead of sleeping.
    """

    def __init__(
        self,
        *,
        failure_threshold: int,
        open_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        self._failure_threshold = failure_threshold
        self._open_seconds = open_seconds
        self._clock = clock
        self._consecutive_failures = 0
        self._open_until = 0.0

    @property
    def is_open(self) -> bool:
        return self._clock() < self._open_until

    def check(self) -> None:
        if self.is_open:
            raise CircuitOpenError(
                f"circuit open for another {self._open_until - self._clock():.1f}s"
            )

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open_until = 0.0

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._failure_threshold:
            self._open_until = self._clock() + self._open_seconds
