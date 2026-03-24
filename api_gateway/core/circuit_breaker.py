"""Circuit Breaker - Prevents cascading failures to downstream services."""

import logging
import time
from enum import Enum
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Blocking requests
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, service: str, time_until_retry: float):
        self.service = service
        self.time_until_retry = time_until_retry
        super().__init__(f"Circuit breaker open for {service}")


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Tracks failures within a time window and opens the circuit
    when failure threshold is exceeded.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: int = 10,
        recovery_timeout: int = 30,
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Service name for logging.
            failure_threshold: Number of failures to trigger open state.
            window_seconds: Time window for counting failures.
            recovery_timeout: Seconds to wait before attempting recovery.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failures: list[float] = []  # Timestamps of failures
        self._last_failure_time: Optional[float] = None
        self._opened_at: Optional[float] = None
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._get_state()

    def _get_state(self) -> CircuitState:
        """Internal state calculation (must hold lock)."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._opened_at:
                elapsed = time.time() - self._opened_at
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
        return self._state

    def _clean_old_failures(self) -> None:
        """Remove failures outside the current window."""
        cutoff = time.time() - self.window_seconds
        self._failures = [f for f in self._failures if f > cutoff]

    def check(self) -> None:
        """
        Check if request should be allowed.

        Raises:
            CircuitBreakerOpen: If circuit is open and should block requests.
        """
        with self._lock:
            state = self._get_state()

            if state == CircuitState.OPEN:
                time_until_retry = 0.0
                if self._opened_at:
                    time_until_retry = max(
                        0,
                        self.recovery_timeout - (time.time() - self._opened_at),
                    )
                raise CircuitBreakerOpen(self.name, time_until_retry)

            # HALF_OPEN allows a single test request
            # CLOSED allows all requests

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery successful
                self._state = CircuitState.CLOSED
                self._failures.clear()
                self._opened_at = None
                logger.info(f"Circuit breaker {self.name} closed after successful recovery")

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            now = time.time()
            self._failures.append(now)
            self._last_failure_time = now

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery attempt
                self._state = CircuitState.OPEN
                self._opened_at = now
                logger.warning(f"Circuit breaker {self.name} re-opened after failed recovery")
                return

            # Check if threshold exceeded
            self._clean_old_failures()
            if len(self._failures) >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = now
                logger.warning(
                    f"Circuit breaker {self.name} opened after {len(self._failures)} "
                    f"failures in {self.window_seconds}s"
                )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failures.clear()
            self._opened_at = None
            logger.info(f"Circuit breaker {self.name} manually reset")

    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        with self._lock:
            self._clean_old_failures()
            return {
                "name": self.name,
                "state": self._get_state().value,
                "failure_count": len(self._failures),
                "failure_threshold": self.failure_threshold,
                "last_failure_time": self._last_failure_time,
                "opened_at": self._opened_at,
            }
