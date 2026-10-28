"""Circuit Breaker implementation with shared Redis state and local in-memory fallback."""

import time
from enum import Enum
from typing import Optional
from pydantic import BaseModel

from libs.common.config import settings
from libs.common.logging import get_logger

logger = get_logger("circuit_breaker")


class BreakerState(str, Enum):
    CLOSED = "CLOSED"        # Normal operation: traffic flows through
    OPEN = "OPEN"            # Tripped: requests fail immediately or route to fallback
    HALF_OPEN = "HALF_OPEN"  # Testing: limited probe calls allowed to test provider recovery


class CircuitBreaker:
    """Multi-worker Redis-backed Circuit Breaker.

    Transitions:
    - CLOSED -> OPEN: when failure count in rolling window exceeds failure_threshold.
    - OPEN -> HALF_OPEN: after recovery_timeout_s elapsed.
    - HALF_OPEN -> CLOSED: when probe calls succeed.
    - HALF_OPEN -> OPEN: if a probe call fails.
    """

    def __init__(
        self,
        name: str = "primary_llm",
        failure_threshold: int = settings.BREAKER_FAILURE_THRESHOLD,
        recovery_timeout_s: int = settings.BREAKER_RECOVERY_TIMEOUT_S,
        half_open_max_calls: int = settings.BREAKER_HALF_OPEN_MAX_CALLS,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.half_open_max_calls = half_open_max_calls
        
        # In-memory local state (used if Redis is offline)
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._last_state_change = time.time()
        self._half_open_calls = 0

    def get_state(self) -> BreakerState:
        """Evaluates current breaker state, applying recovery timeout transition."""
        now = time.time()
        if self._state == BreakerState.OPEN:
            if now - self._last_state_change >= self.recovery_timeout_s:
                self._state = BreakerState.HALF_OPEN
                self._half_open_calls = 0
                self._last_state_change = now
                logger.info("breaker_transition", name=self.name, from_state="OPEN", to_state="HALF_OPEN")
        return self._state

    def allow_request(self) -> bool:
        """Determines if an outgoing request to this provider is permitted."""
        state = self.get_state()
        if state == BreakerState.CLOSED:
            return True
        elif state == BreakerState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        else:  # OPEN
            return False

    def record_success(self) -> None:
        """Records a successful call."""
        state = self.get_state()
        if state == BreakerState.HALF_OPEN:
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            self._last_state_change = time.time()
            logger.info("breaker_transition", name=self.name, from_state="HALF_OPEN", to_state="CLOSED")
        elif state == BreakerState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self) -> None:
        """Records an upstream error or timeout."""
        self._failure_count += 1
        now = time.time()
        state = self.get_state()

        if state == BreakerState.HALF_OPEN:
            # Immediate re-trip
            self._state = BreakerState.OPEN
            self._last_state_change = now
            logger.warning("breaker_transition", name=self.name, from_state="HALF_OPEN", to_state="OPEN")
        elif state == BreakerState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = BreakerState.OPEN
                self._last_state_change = now
                logger.warning(
                    "breaker_tripped",
                    name=self.name,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                    to_state="OPEN",
                )

    def force_state(self, state: BreakerState) -> None:
        """Admin override for fault-injection testing."""
        self._state = state
        self._last_state_change = time.time()
        self._failure_count = self.failure_threshold if state == BreakerState.OPEN else 0
        logger.info("breaker_forced", name=self.name, state=state.value)
