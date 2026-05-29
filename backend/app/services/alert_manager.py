import enum
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.core.metrics import (
    signals_total, executions_total, risk_rejections_total, integrity_failures_total,
    trace_persist_failures_total, recovery_loop_errors_total, dlq_size,
    pel_depth, consumer_pending, redis_aof_enabled, stream_length,
)
from app.services.notification_service import NotificationService


class AlertSeverity(enum.Enum):
    PAGE = "page"
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class AlertRule:
    name: str
    severity: AlertSeverity
    condition_fn: callable
    cooldown_seconds: int = 300
    description: str = ""
    runbook: str = ""


@dataclass
class AlertEvent:
    rule_name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime
    acknowledged: bool = False


ALERT_RULES: list[AlertRule] = []


class AlertManager:
    def __init__(self, notification_service: NotificationService | None = None):
        self._notification = notification_service or NotificationService()
        self._last_fired: dict[str, float] = {}
        self._alert_history: deque[AlertEvent] = deque(maxlen=200)
        self._suppression_counts: dict[str, int] = defaultdict(int)

    def register_rule(self, rule: AlertRule):
        ALERT_RULES.append(rule)

    def register_rules(self, rules: list[AlertRule]):
        for rule in rules:
            self.register_rule(rule)

    async def evaluate_all(self, metrics_snapshot: dict[str, Any] | None = None):
        now = time.monotonic()
        for rule in ALERT_RULES:
            try:
                result = rule.condition_fn(metrics_snapshot or {})
                if result:
                    last = self._last_fired.get(rule.name, 0)
                    if now - last < rule.cooldown_seconds:
                        self._suppression_counts[rule.name] += 1
                        continue
                    self._last_fired[rule.name] = now
                    self._suppression_counts[rule.name] = 0

                    event = AlertEvent(
                        rule_name=rule.name,
                        severity=rule.severity,
                        message=result,
                        timestamp=datetime.now(timezone.utc),
                    )
                    self._alert_history.append(event)
                    await self._dispatch(event)
            except Exception as e:
                logger.error("alert_evaluation_error", rule=rule.name, error=str(e))

    async def _dispatch(self, event: AlertEvent):
        logger.warning("alert_fired", rule=event.rule_name, severity=event.severity.value, message=event.message)
        if event.severity in (AlertSeverity.PAGE, AlertSeverity.CRITICAL):
            await self._notification.send_alert(
                f"[{event.severity.value.upper()}] {event.rule_name}: {event.message}",
                level="critical",
            )

    def get_history(self, limit: int = 50) -> list[AlertEvent]:
        return list(self._alert_history)[-limit:]

    def get_suppression_counts(self) -> dict[str, int]:
        return dict(self._suppression_counts)


def build_default_rules() -> list[AlertRule]:
    rules = []

    def _redis_persistence(metrics):
        val = redis_aof_enabled._value.get()
        if val == 0:
            return "Redis AOF persistence disabled. ALL data lost on restart."
        return None
    rules.append(AlertRule("redis_persistence_disabled", AlertSeverity.PAGE, _redis_persistence, description="Redis has no persistence"))

    def _db_pool_exhaustion(metrics):
        from app.core.metrics import db_pool_size
        available = db_pool_size.labels(state="available")._value.get()
        if available is not None and available <= 0:
            return "All DB connections in use. Operations blocking."
        return None
    rules.append(AlertRule("db_pool_exhaustion", AlertSeverity.PAGE, _db_pool_exhaustion, cooldown_seconds=60, description="DB pool exhausted"))

    def _no_ws_events(metrics):
        ws_min = metrics.get("ws_events_per_minute", -1)
        if ws_min == 0:
            return "No WebSocket events received in the last minute."
        return None
    rules.append(AlertRule("no_ws_events", AlertSeverity.CRITICAL, _no_ws_events, cooldown_seconds=300, description="No WS events received"))

    def _drawdown_exceeded(metrics):
        dd = metrics.get("drawdown", 0)
        if dd > 0.15:
            return f"Portfolio drawdown {dd:.2%} exceeds 15% threshold."
        return None
    rules.append(AlertRule("drawdown_exceeded", AlertSeverity.CRITICAL, _drawdown_exceeded, description="Drawdown exceeds 15%"))

    def _dlq_growth(metrics):
        size = dlq_size.labels(origin_stream="market:data")._value.get()
        if size is not None and size > 100:
            return f"DLQ size {size} exceeds 100."
        return None
    rules.append(AlertRule("dlq_growth", AlertSeverity.WARNING, _dlq_growth, cooldown_seconds=900, description="DLQ growing"))

    def _integrity_failures(metrics):
        count = integrity_failures_total._value.get()
        if count and count > 0:
            return f"Integrity assertion failures detected: {count}."
        return None
    rules.append(AlertRule("integrity_failures", AlertSeverity.WARNING, _integrity_failures, description="Data integrity checks failing"))

    def _trace_persist_failures(metrics):
        count = trace_persist_failures_total._value.get()
        if count and count > 0:
            return f"Trace persistence failures detected: {count}."
        return None
    rules.append(AlertRule("trace_persist_failures", AlertSeverity.WARNING, _trace_persist_failures, description="Execution trace persistence failing"))

    return rules


class SLOBurnRateAlert:
    def __init__(self, name: str, severity: AlertSeverity, good_ratio: float, window_seconds: int, burn_rate_threshold: float):
        self.name = name
        self.severity = severity
        self.good_ratio = good_ratio
        self.window_seconds = window_seconds
        self.burn_rate_threshold = burn_rate_threshold
        self._total_events: list[float] = []
        self._bad_events: list[float] = []

    def record_good(self):
        now = time.monotonic()
        self._total_events.append(now)

    def record_bad(self):
        now = time.monotonic()
        self._total_events.append(now)
        self._bad_events.append(now)

    def evaluate(self) -> str | None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._total_events = [t for t in self._total_events if t > cutoff]
        self._bad_events = [t for t in self._bad_events if t > cutoff]
        if not self._total_events:
            return None
        actual_ratio = 1.0 - (len(self._bad_events) / len(self._total_events))
        error_budget_consumed = max(0, self.good_ratio - actual_ratio)
        if self.good_ratio > 0:
            burn_rate = error_budget_consumed / (1.0 - self.good_ratio) if (1.0 - self.good_ratio) > 0 else 999
        else:
            burn_rate = 0
        if burn_rate >= self.burn_rate_threshold:
            return (f"SLO burn-rate {burn_rate:.1f}x for {self.name} "
                    f"(actual={actual_ratio:.4f}, target={self.good_ratio:.4f}, "
                    f"bad={len(self._bad_events)}/{len(self._total_events)})")
        return None


class SymptomAggregator:
    def __init__(self):
        self._active_symptoms: dict[str, list[str]] = {}

    def add_symptom(self, root_cause: str, symptom: str):
        if root_cause not in self._active_symptoms:
            self._active_symptoms[root_cause] = []
        if symptom not in self._active_symptoms[root_cause]:
            self._active_symptoms[root_cause].append(symptom)

    def collapse(self) -> list[str]:
        result = []
        for root_cause, symptoms in self._active_symptoms.items():
            if len(symptoms) > 1:
                result.append(f"PIPELINE DEGRADATION: root cause likely {root_cause} ({len(symptoms)} symptoms)")
            else:
                result.append(f"{root_cause}: {symptoms[0]}")
        self._active_symptoms.clear()
        return result
