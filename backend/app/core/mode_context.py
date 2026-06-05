from dataclasses import dataclass
from enum import Enum


class MetricClass(Enum):
    STRUCTURAL = "structural"
    BEHAVIORAL = "behavioral"
    UNKNOWN = "unknown"


METRIC_CLASSIFICATION: dict[str, MetricClass] = {
    "db_pool_utilization_pct": MetricClass.STRUCTURAL,
    "redis_memory_pct": MetricClass.STRUCTURAL,
    "redis_provider_pct": MetricClass.STRUCTURAL,
    "circuit_breaker_open": MetricClass.STRUCTURAL,
    "db_ok": MetricClass.STRUCTURAL,
    "emergency_stop": MetricClass.STRUCTURAL,
    "kill_switch": MetricClass.STRUCTURAL,
    "drawdown": MetricClass.STRUCTURAL,
    "redis_max_pending": MetricClass.BEHAVIORAL,
    "reconnect_storm": MetricClass.BEHAVIORAL,
    "stream_pressure_ratio": MetricClass.BEHAVIORAL,
}


def classify_metric(key: str) -> MetricClass:
    return METRIC_CLASSIFICATION.get(key, MetricClass.UNKNOWN)


_reported_gaps: set[str] = set()


def adjust_metric(key: str, raw_value: float, sensitivity: float) -> float:
    cls = classify_metric(key)
    if cls == MetricClass.UNKNOWN:
        if key not in _reported_gaps:
            _reported_gaps.add(key)
            from app.core.logging import logger
            from app.core.metrics import metric_classification_unknown_total
            logger.warning("metric_classification_gap", metric=key, default="structural")
            metric_classification_unknown_total.labels(metric_name=key).inc()
        return raw_value
    if cls == MetricClass.BEHAVIORAL:
        return raw_value * sensitivity
    return raw_value


@dataclass(frozen=True)
class ModeContext:
    name: str

    db_pool_warning: float
    db_pool_critical: float

    redis_memory_warning: float
    redis_memory_critical: float

    stream_warning_ratio: float
    stream_critical_ratio: float

    cb_failure_tolerance: float

    evaluator_sensitivity: float


MODE_CONTEXTS: dict[str, ModeContext] = {
    "normal": ModeContext(
        name="NORMAL",
        db_pool_warning=0.70,
        db_pool_critical=0.85,
        redis_memory_warning=0.70,
        redis_memory_critical=0.85,
        stream_warning_ratio=0.70,
        stream_critical_ratio=0.90,
        cb_failure_tolerance=10,
        evaluator_sensitivity=1.0,
    ),
    "degraded": ModeContext(
        name="DEGRADED",
        db_pool_warning=0.80,
        db_pool_critical=0.90,
        redis_memory_warning=0.80,
        redis_memory_critical=0.90,
        stream_warning_ratio=0.80,
        stream_critical_ratio=0.95,
        cb_failure_tolerance=20,
        evaluator_sensitivity=0.6,
    ),
    "protected": ModeContext(
        name="PROTECTED",
        db_pool_warning=0.85,
        db_pool_critical=0.95,
        redis_memory_warning=0.85,
        redis_memory_critical=0.95,
        stream_warning_ratio=0.90,
        stream_critical_ratio=0.98,
        cb_failure_tolerance=30,
        evaluator_sensitivity=0.3,
    ),
    "read_only": ModeContext(
        name="READ_ONLY",
        db_pool_warning=1.0,
        db_pool_critical=1.0,
        redis_memory_warning=1.0,
        redis_memory_critical=1.0,
        stream_warning_ratio=1.0,
        stream_critical_ratio=1.0,
        cb_failure_tolerance=100,
        evaluator_sensitivity=0.0,
    ),
    "emergency_stop": ModeContext(
        name="EMERGENCY_STOP",
        db_pool_warning=1.0,
        db_pool_critical=1.0,
        redis_memory_warning=1.0,
        redis_memory_critical=1.0,
        stream_warning_ratio=1.0,
        stream_critical_ratio=1.0,
        cb_failure_tolerance=1000,
        evaluator_sensitivity=0.0,
    ),
}


_MIN_MODE_HOLD_TIME: dict[str, float] = {
    "normal": 0.0,
    "degraded": 60.0,
    "protected": 120.0,
    "read_only": 300.0,
    "emergency_stop": 10.0,
}


def get_hold_time(mode_name: str) -> float:
    return _MIN_MODE_HOLD_TIME.get(mode_name, 60.0)
