import functools
from time import perf_counter_ns

from app.core.metrics import (
    ws_ingest_latency,
    signal_generation_latency,
    risk_evaluation_latency,
    execution_latency,
    persistence_latency,
    allocation_latency,
    db_query_latency,
    end_to_end_latency,
    event_to_execution_latency,
)

_HISTOGRAM_MAP = {
    "ws_ingest": ws_ingest_latency,
    "signal_generation": signal_generation_latency,
    "risk_evaluation": risk_evaluation_latency,
    "execution": execution_latency,
    "persistence": persistence_latency,
    "allocation": allocation_latency,
    "db_query": db_query_latency,
    "end_to_end": end_to_end_latency,
    "event_to_execution": event_to_execution_latency,
}


def timed(name: str, labels: dict[str, str] | None = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = perf_counter_ns()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed_ms = (perf_counter_ns() - start) / 1_000_000
                histogram = _HISTOGRAM_MAP.get(name)
                if histogram is not None:
                    if labels:
                        histogram.labels(**labels).observe(elapsed_ms)
                    else:
                        histogram.observe(elapsed_ms)
        return wrapper
    return decorator


def record_latency(name: str, duration_ms: float, labels: dict[str, str] | None = None):
    histogram = _HISTOGRAM_MAP.get(name)
    if histogram is not None:
        if labels:
            histogram.labels(**labels).observe(duration_ms)
        else:
            histogram.observe(duration_ms)
