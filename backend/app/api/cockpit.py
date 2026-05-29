from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func as sa_func, desc
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from app.core.system_mode import get_mode_manager, SystemMode, _MODE_ORDER
from app.database import async_session_factory
from app.models.system_mode import SystemModeTransition
from app.core.metrics import mode_flips_total, mode_escalation_chain_depth, mode_proposal_rejected_total
from app.services.pipeline_metrics import get_metrics as get_pipeline_metrics

router = APIRouter()

_MODE_COLORS = {
    "normal": "#00C853",
    "degraded": "#FFD600",
    "protected": "#FF9800",
    "read_only": "#9C27B0",
    "emergency_stop": "#FF1744",
}


@router.get("/overview")
async def cockpit_overview():
    mgr = get_mode_manager()
    snapshot = await mgr.get_snapshot()
    ctx = MODE_CONTEXTS.get(snapshot.mode.value)
    sensitivity = ctx.evaluator_sensitivity if ctx else 1.0

    # recent transitions from DB
    async with async_session_factory() as db:
        result = await db.execute(
            select(SystemModeTransition)
            .order_by(desc(SystemModeTransition.created_at))
            .limit(50)
        )
        transitions = list(result.scalars().all())

    # Prometheus metric values via registry
    try:
        from prometheus_client.registry import REGISTRY
        flip_count = int(REGISTRY.get_sample_value("polymarket_mode_flips_total") or 0)
        chain_depth = int(REGISTRY.get_sample_value("polymarket_mode_escalation_chain_depth") or 0)
        hysteresis_rejected = int(
            REGISTRY.get_sample_value(
                "polymarket_mode_proposal_rejected_total",
                {"reason": "hysteresis"}
            ) or 0
        )
    except Exception:
        flip_count = 0
        chain_depth = 0
        hysteresis_rejected = 0

    pipeline = await get_pipeline_metrics()

    # time in each mode from transition durations
    time_in_mode = _compute_time_in_mode(transitions)

    return {
        "current_mode": {
            "mode": snapshot.mode.value,
            "reason": snapshot.reason,
            "is_manual_override": snapshot.is_manual_override,
            "operator": snapshot.operator or "",
            "updated_at": snapshot.updated_at,
            "ttl_seconds": snapshot.ttl_seconds,
            "color": _MODE_COLORS.get(snapshot.mode.value, "#888888"),
            "sensitivity": sensitivity,
        },
        "recent_transitions": [
            {
                "id": str(t.id),
                "from_mode": t.from_mode,
                "to_mode": t.to_mode,
                "reason": t.reason or "",
                "is_manual": t.is_manual,
                "operator": t.operator or "",
                "duration_seconds": t.duration_seconds,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in transitions
        ],
        "stability_metrics": {
            "flip_count": flip_count,
            "escalation_chain_depth": chain_depth,
            "hysteresis_rejected_count": hysteresis_rejected,
            "time_in_mode_pct": time_in_mode,
            "total_transitions_24h": len(transitions),
        },
        "pipeline": {
            k: v for k, v in pipeline.items()
            if k in ("signal_rate_per_minute", "risk_rejection_rate",
                     "execution_success_rate", "health_alerts_count",
                     "total_open_exposure", "exposure_utilization_pct",
                     "live_state")
        },
        "recorded_snapshots_count": 0,
    }


@router.get("/instability")
async def cockpit_instability(window_minutes: int = Query(30, ge=5, le=1440)):
    mgr = get_mode_manager()
    snapshot = await mgr.get_snapshot()
    current_mode = snapshot.mode.value

    # recent transitions in window
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    async with async_session_factory() as db:
        result = await db.execute(
            select(SystemModeTransition)
            .where(SystemModeTransition.created_at >= cutoff)
            .order_by(SystemModeTransition.created_at)
        )
        recent = list(result.scalars().all())

    try:
        from prometheus_client.registry import REGISTRY
        flip_count = int(REGISTRY.get_sample_value("polymarket_mode_flips_total") or 0)
        chain_depth = int(REGISTRY.get_sample_value("polymarket_mode_escalation_chain_depth") or 0)
        hysteresis_rejected = int(
            REGISTRY.get_sample_value(
                "polymarket_mode_proposal_rejected_total",
                {"reason": "hysteresis"}
            ) or 0
        )
    except Exception:
        flip_count = 0
        chain_depth = 0
        hysteresis_rejected = 0

    flip_rate = flip_count / max(window_minutes, 1)

    oscillation_detected, oscillation_count = _detect_oscillation(recent)

    is_protective = current_mode in ("protected", "emergency_stop", "read_only")
    has_override = snapshot.is_manual_override

    # composite instability score (0 = stable, 1 = unstable)
    score = 0.0
    drivers = []

    if flip_count > 5:
        score += 0.35
        drivers.append(f"High flip count ({flip_count})")
    elif flip_count > 1:
        score += 0.15
        drivers.append(f"Elevated flips ({flip_count})")

    if chain_depth >= 3:
        score += 0.20
        drivers.append(f"Deep escalation chain ({chain_depth})")
    elif chain_depth >= 1:
        score += 0.08

    if oscillation_detected:
        score += 0.30
        drivers.append(f"Oscillation detected ({oscillation_count} events)")

    if hysteresis_rejected > 10:
        score += 0.15
        drivers.append(f"High hysteresis rejection ({hysteresis_rejected})")

    if flip_rate > 0.5:
        score += 0.15
        drivers.append(f"Rapid mode switching ({flip_rate:.1f}/min)")

    if is_protective and has_override:
        score += 0.10
        drivers.append("Manual override in protective mode")

    score = min(score, 1.0)

    if score <= 0.2:
        state = "stable"
        status_message = "System stable"
    elif score <= 0.5:
        state = "watch"
        status_message = "Feedback loop active"
    else:
        state = "unstable"
        status_message = "Oscillation risk detected"

    return {
        "instability_score": round(score, 3),
        "state": state,
        "status_message": status_message,
        "primary_drivers": drivers[:3],
        "indicators": {
            "flip_count": flip_count,
            "flip_rate_per_min": round(flip_rate, 3),
            "chain_depth": chain_depth,
            "hysteresis_rejected": hysteresis_rejected,
            "oscillation_detected": oscillation_detected,
            "oscillation_events": oscillation_count,
        },
        "current_mode": current_mode,
        "has_override": has_override,
        "trend": _compute_trend(recent) if recent else "stable",
    }


@router.get("/explanation")
async def cockpit_explanation():
    mgr = get_mode_manager()
    snapshot = await mgr.get_snapshot()

    async with async_session_factory() as db:
        result = await db.execute(
            select(SystemModeTransition)
            .order_by(desc(SystemModeTransition.created_at))
            .limit(5)
        )
        transitions = list(result.scalars().all())

    ctx = MODE_CONTEXTS.get(snapshot.mode.value)

    last = transitions[0] if transitions else None

    primary_driver = _determine_primary_driver(last, snapshot, ctx)
    factors = _get_contributing_factors(snapshot.mode.value, ctx)

    human_readable = _build_summary(snapshot, last, primary_driver)

    return {
        "current_mode": snapshot.mode.value,
        "is_manual_override": snapshot.is_manual_override,
        "primary_driver": primary_driver,
        "contributing_factors": factors,
        "transition_summary": human_readable,
        "last_transition": {
            "from_mode": last.from_mode if last else None,
            "to_mode": last.to_mode if last else None,
            "reason": last.reason if last else None,
            "created_at": last.created_at.isoformat() if last and last.created_at else None,
            "is_manual": last.is_manual if last else False,
        } if last else None,
        "mode_color": _MODE_COLORS.get(snapshot.mode.value, "#888888"),
    }


# ── helpers ─────────────────────────────────────────

from app.core.mode_context import MODE_CONTEXTS


def _compute_time_in_mode(transitions: list[SystemModeTransition]) -> dict[str, float]:
    if not transitions:
        return {}
    total = 0.0
    durations: dict[str, float] = {}
    for t in transitions:
        if t.duration_seconds:
            durations[t.to_mode] = durations.get(t.to_mode, 0) + t.duration_seconds
            total += t.duration_seconds
    if total == 0:
        return {}
    return {m: round((d / total) * 100, 1) for m, d in sorted(durations.items())}


def _detect_oscillation(transitions: list[SystemModeTransition], min_flips: int = 2) -> tuple[bool, int]:
    if len(transitions) < 3:
        return False, 0
    flips = 0
    for i in range(1, len(transitions)):
        prev_idx = _MODE_ORDER.index(SystemMode(transitions[i - 1].from_mode))
        prev_to_idx = _MODE_ORDER.index(SystemMode(transitions[i - 1].to_mode))
        curr_idx = _MODE_ORDER.index(SystemMode(transitions[i].from_mode))
        curr_to_idx = _MODE_ORDER.index(SystemMode(transitions[i].to_mode))
        prev_dir = prev_to_idx - prev_idx
        curr_dir = curr_to_idx - curr_idx
        if prev_dir * curr_dir < 0:
            flips += 1
    return flips >= min_flips, flips


def _compute_trend(transitions: list[SystemModeTransition]) -> str:
    recent = transitions[-10:] if len(transitions) >= 10 else transitions
    if not recent:
        return "stable"
    upward = 0
    downward = 0
    for t in recent:
        from_idx = _MODE_ORDER.index(SystemMode(t.from_mode))
        to_idx = _MODE_ORDER.index(SystemMode(t.to_mode))
        if to_idx > from_idx:
            upward += 1
        elif to_idx < from_idx:
            downward += 1
    if upward > downward * 2:
        return "worsening"
    if downward > upward * 2:
        return "improving"
    return "stable"


def _determine_primary_driver(last_transition, snapshot, ctx) -> str:
    if snapshot.is_manual_override:
        return f"Manual override by {snapshot.operator or 'unknown'}"
    if last_transition:
        reason = last_transition.reason or ""
        if "db_pool" in reason:
            return "Database pool pressure"
        if "redis" in reason:
            return "Redis memory or pending pressure"
        if "drawdown" in reason:
            return "Portfolio drawdown"
        if "stream" in reason:
            return "Stream pipeline pressure"
        if "reconnect" in reason:
            return "Reconnection storm"
        if "circuit_breaker" in reason:
            return "Circuit breaker open"
        if "emergency" in reason or "kill" in reason:
            return "Emergency stop or kill switch"
        if last_transition.is_manual:
            return f"Manual action by {last_transition.operator or 'unknown'}"
        return reason.replace("_", " ").title()
    return "Initial startup"


def _get_contributing_factors(mode: str, ctx) -> list[dict]:
    factors = []
    if ctx:
        sensitivity = ctx.evaluator_sensitivity
        factors.append({
            "factor": "evaluator_sensitivity",
            "value": sensitivity,
            "impact": "low" if sensitivity < 0.5 else "medium" if sensitivity < 0.8 else "high",
        })
    from app.core.mode_context import METRIC_CLASSIFICATION
    for metric_key, classification in METRIC_CLASSIFICATION.items():
        factors.append({
            "factor": metric_key,
            "classification": classification.value,
            "impact": "medium",
        })
    return factors


def _build_summary(snapshot, last_transition, primary_driver: str) -> str:
    parts = []
    if snapshot.is_manual_override:
        parts.append(f"System is in {snapshot.mode.value.upper()} mode due to manual override.")
    elif last_transition:
        parts.append(
            f"Transitioned from {last_transition.from_mode.upper()} to {last_transition.to_mode.upper()}: "
            f"{last_transition.reason or 'no reason recorded'}."
        )
    else:
        parts.append(f"System is in {snapshot.mode.value.upper()} mode.")
    parts.append(f"Primary driver: {primary_driver}.")
    if snapshot.ttl_seconds:
        parts.append(f"Override expires in {snapshot.ttl_seconds}s.")
    return " ".join(parts)
