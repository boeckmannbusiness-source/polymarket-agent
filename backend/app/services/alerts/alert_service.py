import uuid
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

from app.core.logging import logger
from app.redis import get_redis
from app.services.alerts.rules import AlertRule, build_all_rules
from app.services.stream.event_store import event_store


ALERT_STORE_KEY = "alert:history"
ALERT_MAX_HISTORY = 2000


class AlertService:
    def __init__(self):
        self._rules: list[AlertRule] = []
        self._alert_history: list[dict[str, Any]] = []
        self._cooldowns: dict[str, float] = {}
        self._entity_cooldowns: dict[str, dict[str, float]] = defaultdict(dict)
        self._escalation_counts: dict[str, int] = defaultdict(int)
        self._max_history = ALERT_MAX_HISTORY
        self._dedup_window: dict[str, float] = {}

    def register_rules(self, rules: list[AlertRule]):
        self._rules.extend(rules)

    def register_default_rules(self):
        self.register_rules(build_all_rules())

    async def evaluate(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).timestamp()
        triggered: list[dict[str, Any]] = []

        for rule in self._rules:
            if not self._check_rule_cooldown(rule, now):
                continue

            try:
                results = rule.evaluate(context)
            except Exception as e:
                logger.warning("alert_rule_eval_failed", rule=rule.name, error=str(e))
                continue

            for result in results:
                entity_id = result.get("entity_id", "global")

                if not self._check_entity_cooldown(rule, entity_id, now):
                    continue

                severity = self._get_effective_severity(rule, entity_id)

                if self._is_spam(entity_id, rule.name, now):
                    continue

                alert = {
                    "id": str(uuid.uuid4()),
                    "rule": rule.name,
                    "severity": severity,
                    "type": rule.alert_type,
                    "category": rule.alert_type,
                    "title": f"[{severity.upper()}] {rule.description}",
                    "message": result.get("message", ""),
                    "entity_id": entity_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "triggered",
                    "acknowledged": False,
                    "escalation_level": self._escalation_counts.get(f"{rule.name}:{entity_id}", 0),
                }
                triggered.append(alert)
                self._alert_history.append(alert)
                self._cooldowns[rule.name] = now
                self._entity_cooldowns[rule.name][entity_id] = now
                self._dedup_window[f"{entity_id}:{rule.name}"] = now
                self._escalation_counts[f"{rule.name}:{entity_id}"] += 1

                await event_store.store({
                    "event_id": alert["id"],
                    "event_type": "alert.created",
                    "entity_type": "alert",
                    "entity_id": entity_id,
                    "sequence": 0,
                    "timestamp": alert["timestamp"],
                    "payload": alert,
                })

                logger.info("alert_triggered", rule=rule.name, severity=severity, entity=entity_id)

        self._trim_history()
        return triggered

    def _check_rule_cooldown(self, rule: AlertRule, now: float) -> bool:
        last_fired = self._cooldowns.get(rule.name, 0)
        return (now - last_fired) >= rule.cooldown_seconds

    def _check_entity_cooldown(self, rule: AlertRule, entity_id: str, now: float) -> bool:
        entity_cd = self._entity_cooldowns.get(rule.name, {}).get(entity_id, 0)
        min_cd = max(10, rule.cooldown_seconds // 3)
        return (now - entity_cd) >= min_cd

    def _get_effective_severity(self, rule: AlertRule, entity_id: str) -> str:
        key = f"{rule.name}:{entity_id}"
        count = self._escalation_counts.get(key, 0)

        severity_order = ["info", "warning", "critical"]
        base_idx = severity_order.index(rule.severity) if rule.severity in severity_order else 0
        escalated_idx = min(base_idx + (count // 3), len(severity_order) - 1)
        return severity_order[escalated_idx]

    def _is_spam(self, entity_id: str, rule_name: str, now: float) -> bool:
        last = self._dedup_window.get(f"{entity_id}:{rule_name}", 0)
        return (now - last) < 5

    def get_history(self, limit: int = 50, severity: str | None = None) -> list[dict]:
        alerts = list(reversed(self._alert_history))
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts[:limit]

    def get_unacknowledged(self) -> list[dict]:
        return [a for a in self._alert_history if not a.get("acknowledged")]

    def acknowledge(self, alert_id: str) -> bool:
        for alert in self._alert_history:
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                alert["status"] = "acknowledged"
                return True
        return False

    def dismiss(self, alert_id: str) -> bool:
        for alert in self._alert_history:
            if alert["id"] == alert_id:
                alert["status"] = "resolved"
                return True
        return False

    def resolve_all_for_entity(self, entity_id: str):
        for alert in self._alert_history:
            if alert.get("entity_id") == entity_id and alert["status"] in ("triggered", "acknowledged"):
                alert["status"] = "resolved"

    def get_stats(self) -> dict[str, Any]:
        total = len(self._alert_history)
        by_severity: dict[str, int] = defaultdict(int)
        by_status: dict[str, int] = defaultdict(int)
        for a in self._alert_history:
            by_severity[a.get("severity", "unknown")] += 1
            by_status[a.get("status", "triggered")] += 1
        return {
            "total": total,
            "by_severity": dict(by_severity),
            "by_status": dict(by_status),
            "unacknowledged": len(self.get_unacknowledged()),
        }

    def _trim_history(self):
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history:]


alert_service = AlertService()
