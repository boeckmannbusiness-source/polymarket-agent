import logging
import random
import re
import time
from collections import defaultdict
from contextvars import ContextVar

import structlog
from app.config import settings


_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")
_event_type: ContextVar[str] = ContextVar("event_type", default="")
_strategy: ContextVar[str] = ContextVar("strategy", default="")

WALLET_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")


def scrub_wallets(text: str) -> str:
    return WALLET_PATTERN.sub(lambda m: m.group()[:8] + "...", text)


class ContextFilter(logging.Filter):
    def filter(self, record):
        record.correlation_id = _correlation_id.get() or ""
        record.event_type = _event_type.get() or ""
        record.strategy = _strategy.get() or ""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = scrub_wallets(record.msg)
        return True


class StormSuppressor:
    def __init__(self, window: int = 60, max_per_window: int = 5):
        self._window = window
        self._max = max_per_window
        self._counts: dict[str, list[float]] = defaultdict(list)

    def should_log(self, key: str) -> bool:
        now = time.monotonic()
        self._counts[key] = [t for t in self._counts[key] if now - t < self._window]
        if len(self._counts[key]) >= self._max:
            return False
        self._counts[key].append(now)
        return True

    def suppressed_count(self, key: str) -> int:
        return len(self._counts.get(key, []))


class SampledLogger:
    def __init__(self, sample_rate: float = 1.0):
        self._sample_rate = sample_rate
        self._rng = random.Random()

    def info(self, msg: str, **kwargs):
        if self._sample_rate >= 1.0 or self._rng.random() < self._sample_rate:
            logger.info(msg, **kwargs)


_suppressor = StormSuppressor()


def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            (
                structlog.processors.JSONRenderer()
                if settings.LOG_FORMAT == "json"
                else structlog.dev.ConsoleRenderer()
            ),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    root_logger = logging.getLogger()
    root_logger.addFilter(ContextFilter())

    return _suppressor


logger = structlog.get_logger()
