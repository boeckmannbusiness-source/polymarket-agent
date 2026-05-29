import enum
import time


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 10, window_seconds: int = 60, recovery_seconds: int = 30):
        self.name = name
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._recovery_seconds = recovery_seconds
        self._state = CircuitState.CLOSED
        self._failures: list[float] = []
        self._last_open_time: float | None = None
        self._total_opens = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._last_open_time:
            if time.monotonic() - self._last_open_time >= self._recovery_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state

    def record_failure(self):
        now = time.monotonic()
        self._failures = [t for t in self._failures if now - t < self._window_seconds]
        self._failures.append(now)
        if len(self._failures) >= self._failure_threshold:
            if self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                self._last_open_time = now
                self._total_opens += 1

    def record_success(self):
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failures.clear()

    def reset(self):
        self._state = CircuitState.CLOSED
        self._failures.clear()

    @property
    def failure_rate(self) -> float:
        now = time.monotonic()
        recent = [t for t in self._failures if now - t < self._window_seconds]
        return len(recent) / max(self._window_seconds, 1)

    @property
    def total_opens(self) -> int:
        return self._total_opens
