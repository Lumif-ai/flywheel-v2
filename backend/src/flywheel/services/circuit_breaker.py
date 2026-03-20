"""Circuit breaker for Anthropic API resilience.

Prevents cascading failures during API outages by tracking consecutive
failures and temporarily blocking requests. Three states:

- CLOSED: Normal operation, requests pass through.
- OPEN: Too many failures, requests blocked until recovery timeout.
- HALF-OPEN: Recovery probe -- one request allowed to test if API is back.

Thread-safe via threading.Lock (called from async tasks via asyncio.to_thread).
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and requests are blocked."""

    pass


class CircuitBreaker:
    """Tracks consecutive Anthropic API failures and trips open after threshold.

    Args:
        failure_threshold: Number of consecutive failures before opening circuit.
        recovery_timeout: Seconds to wait in open state before allowing a probe.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60,
    ) -> None:
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout

    def can_execute(self) -> bool:
        """Check whether a request is allowed through the breaker.

        Returns True if closed or half-open (probe). Returns False if open
        and recovery timeout has not yet elapsed.
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if (
                    self._last_failure_time is not None
                    and time.monotonic() - self._last_failure_time
                    >= self._recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        "Circuit breaker transitioning to half-open (recovery probe)"
                    )
                    return True
                return False

            # HALF_OPEN -- allow the probe request
            return True

    def record_success(self) -> None:
        """Record a successful API call. Resets breaker to closed."""
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed API call. Trips to open if threshold exceeded."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self._failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        "Circuit breaker OPEN after %d consecutive failures. "
                        "Blocking Anthropic API calls for %ds.",
                        self._failure_count,
                        self._recovery_timeout,
                    )
                self._state = CircuitState.OPEN

    def get_status(self) -> dict:
        """Return current breaker state for health check introspection."""
        with self._lock:
            return {
                "state": self._state.value,
                "failures": self._failure_count,
                "last_failure": self._last_failure_time,
            }


# Singleton used by chat orchestrator and skill executor
anthropic_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
