from typing import Any, Callable
from dataclasses import dataclass, field


AlertAction = Callable[[dict], None]


@dataclass
class AlertRule:
    name: str
    severity: str  # info | warning | critical
    alert_type: str  # execution | risk | system
    description: str
    evaluate: Callable[[dict[str, Any]], list[dict[str, Any]]]
    cooldown_seconds: int = 300


EXECUTION_RULES = [
    AlertRule(
        name="order_stuck",
        severity="warning",
        alert_type="execution",
        description="Order stuck in pending/submitted for too long",
        cooldown_seconds=300,
        evaluate=lambda ctx: [
            {
                "message": f"Order {o['order_id']} stuck in {o['status']} for {o.get('age_seconds', 0)}s",
                "entity_id": o["order_id"],
            }
            for o in ctx.get("active_orders", [])
            if o.get("age_seconds", 0) > 300 and o.get("status") in ("pending", "submitted")
        ],
    ),
    AlertRule(
        name="fill_latency_spike",
        severity="warning",
        alert_type="execution",
        description="Fill latency exceeds threshold",
        cooldown_seconds=300,
        evaluate=lambda ctx: [
            {
                "message": f"Fill latency spike: {l.get('latency_ms', 0)}ms for fill {l.get('fill_id', 'unknown')}",
                "entity_id": l.get("fill_id", "unknown"),
            }
            for l in ctx.get("recent_fills", [])
            if l.get("latency_ms", 0) > 5000
        ],
    ),
    AlertRule(
        name="retry_explosion",
        severity="critical",
        alert_type="execution",
        description="Order retry count exceeds threshold",
        cooldown_seconds=120,
        evaluate=lambda ctx: [
            {
                "message": f"Order {o['order_id']} has {o['retry_count']} retries",
                "entity_id": o["order_id"],
            }
            for o in ctx.get("active_orders", [])
            if o.get("retry_count", 0) >= 3
        ],
    ),
]

RISK_RULES = [
    AlertRule(
        name="exposure_threshold",
        severity="warning",
        alert_type="risk",
        description="Portfolio exposure exceeds threshold",
        cooldown_seconds=300,
        evaluate=lambda ctx: [
            {
                "message": f"Exposure ${ctx.get('total_exposure', 0):.2f} exceeds threshold",
                "entity_id": "portfolio",
            }
        ] if ctx.get("total_exposure", 0) > ctx.get("exposure_limit", float("inf")) else [],
    ),
    AlertRule(
        name="drawdown_breach",
        severity="critical",
        alert_type="risk",
        description="Drawdown exceeds maximum allowed",
        cooldown_seconds=300,
        evaluate=lambda ctx: [
            {
                "message": f"Drawdown {(ctx.get('drawdown', 0) * 100):.1f}% exceeds limit",
                "entity_id": "portfolio",
            }
        ] if ctx.get("drawdown", 0) > ctx.get("drawdown_limit", 1.0) else [],
    ),
    AlertRule(
        name="concentration_risk",
        severity="warning",
        alert_type="risk",
        description="Single market concentration too high",
        cooldown_seconds=600,
        evaluate=lambda ctx: [
            {
                "message": f"Concentration risk {ctx.get('concentration_pct', 0):.1f}% exceeds {ctx.get('concentration_limit', 30)}%",
                "entity_id": "portfolio",
            }
        ] if ctx.get("concentration_pct", 0) > ctx.get("concentration_limit", 30) else [],
    ),
]

SYSTEM_RULES = [
    AlertRule(
        name="reconciliation_mismatch",
        severity="critical",
        alert_type="system",
        description="Reconciliation detected mismatch",
        cooldown_seconds=600,
        evaluate=lambda ctx: [
            {
                "message": f"Reconciliation mismatch: {ctx.get('mismatch_count', 0)} issues detected",
                "entity_id": "reconciliation",
            }
        ] if ctx.get("mismatch_detected", False) else [],
    ),
    AlertRule(
        name="drift_detected",
        severity="warning",
        alert_type="system",
        description="Order drift detected by monitoring",
        cooldown_seconds=300,
        evaluate=lambda ctx: ctx.get("drift_alerts", []),
    ),
    AlertRule(
        name="stale_portfolio_snapshot",
        severity="info",
        alert_type="system",
        description="Portfolio snapshot is stale",
        cooldown_seconds=600,
        evaluate=lambda ctx: [
            {
                "message": f"Portfolio snapshot stale for {ctx.get('snapshot_age_seconds', 0)}s",
                "entity_id": "portfolio",
            }
        ] if ctx.get("snapshot_age_seconds", 0) > 3600 else [],
    ),
]


def build_all_rules() -> list[AlertRule]:
    return EXECUTION_RULES + RISK_RULES + SYSTEM_RULES
