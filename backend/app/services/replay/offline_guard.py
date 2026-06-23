from contextvars import ContextVar
from contextlib import contextmanager

# ContextVar to track if we are in a replay context
_REPLAY_ACTIVE: ContextVar[bool] = ContextVar("replay_active", default=False)

class ReplayIsolationViolation(Exception):
    """Raised when an RPC call is attempted during replay."""
    pass

class ReplayOfflineGuard:
    """Guard to ensure replay remains offline."""

    @staticmethod
    def is_replay_active() -> bool:
        return _REPLAY_ACTIVE.get()

    @staticmethod
    @contextmanager
    def enforce():
        """Context manager to enable replay isolation."""
        token = _REPLAY_ACTIVE.set(True)
        try:
            yield
        finally:
            _REPLAY_ACTIVE.reset(token)
