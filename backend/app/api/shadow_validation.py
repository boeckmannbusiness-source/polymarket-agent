from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.core.logging import logger
from app.services.validation.shadow_validation_service import shadow_validation_service
from app.services.validation.shadow_runtime_monitor import shadow_runtime_monitor
from app.services.safety.execution_safety_gate import execution_safety_gate

router = APIRouter()


class FailureInjectionRequest(BaseModel):
    test_name: str
    active: bool


@router.get("/decisions")
async def get_shadow_decisions(
    since: str | None = Query(None, description="ISO timestamp filter"),
    until: str | None = Query(None, description="ISO timestamp filter"),
    limit: int = Query(100, le=10000),
    db: AsyncSession = Depends(get_db),
):
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    logs = await shadow_validation_service.get_decision_logs(
        db=db, since=since_dt, until=until_dt, limit=limit
    )
    return {
        "decisions": [
            {
                "id": str(log.id),
                "timestamp": log.timestamp.isoformat() if log.timestamp else "",
                "market_id": log.market_id,
                "strategy_id": log.strategy_id,
                "signal_source": log.signal_source,
                "regime": log.regime,
                "regime_confidence": log.regime_confidence,
                "expected_return": log.expected_return,
                "optimization_weight": log.optimization_weight,
                "stability_score": log.stability_score,
                "drift_score": log.drift_score,
                "exposure_level": log.exposure_level,
                "safety_gate_decision": log.safety_gate_decision,
                "approval_reason": log.approval_reason,
                "rejection_reason": log.rejection_reason,
            }
            for log in logs
        ],
        "total": len(logs),
    }


@router.get("/metrics")
async def get_shadow_validation_metrics(db: AsyncSession = Depends(get_db)):
    return {
        "execution": await shadow_validation_service.get_execution_metrics(db),
        "safety": await shadow_validation_service.get_safety_metrics(db),
        "regime": await shadow_validation_service.get_regime_metrics(db),
        "optimization": await shadow_validation_service.get_optimization_metrics(db),
        "control_layer": await shadow_validation_service.get_control_layer_metrics(db),
        "gate_metrics": execution_safety_gate.get_metrics_snapshot(),
    }


@router.get("/completeness")
async def get_logging_completeness(db: AsyncSession = Depends(get_db)):
    return await shadow_validation_service.check_logging_completeness(db)


@router.get("/report")
async def get_shadow_validation_report(db: AsyncSession = Depends(get_db)):
    return await shadow_validation_service.generate_report(db)


@router.get("/failure-injection/status")
async def get_failure_injection_status():
    return await shadow_validation_service.get_failure_injection_status()


@router.post("/failure-injection")
async def set_failure_injection(request: FailureInjectionRequest):
    valid_tests = [
        "remove_regime_data",
        "inject_low_confidence",
        "inject_high_drift",
        "simulate_redis_outage",
        "simulate_valkey_outage",
    ]
    if request.test_name not in valid_tests:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid test. Valid: {valid_tests}",
        )
    shadow_validation_service.set_injection_state(request.test_name, request.active)
    logger.warning("failure_injection_set", test=request.test_name, active=request.active)
    return {"test": request.test_name, "active": request.active}


@router.post("/failure-injection/test1")
async def failure_test1_remove_regime_data(db: AsyncSession = Depends(get_db)):
    """Remove regime data. Expected: NO TRADE - Safety gate blocks execution."""
    shadow_validation_service.set_injection_state("remove_regime_data", True)
    from app.services.shadow.shadow_execution_service import shadow_execution_service
    await shadow_execution_service._ensure_redis()
    logger.warning("failure_test_1_remove_regime_data_activated")
    return {"test": "remove_regime_data", "status": "activated", "expected": "NO TRADE - Safety gate blocks execution"}


@router.post("/failure-injection/test2")
async def failure_test2_inject_low_confidence(db: AsyncSession = Depends(get_db)):
    """Inject LOW confidence regime. Expected: NO TRADE."""
    shadow_validation_service.set_injection_state("inject_low_confidence", True)
    logger.warning("failure_test_2_inject_low_confidence_activated")
    return {"test": "inject_low_confidence", "status": "activated", "expected": "NO TRADE"}


@router.post("/failure-injection/test3")
async def failure_test3_inject_high_drift(db: AsyncSession = Depends(get_db)):
    """Inject HIGH drift. Expected: NO TRADE."""
    shadow_validation_service.set_injection_state("inject_high_drift", True)
    logger.warning("failure_test_3_inject_high_drift_activated")
    return {"test": "inject_high_drift", "status": "activated", "expected": "NO TRADE"}


@router.post("/failure-injection/test4")
async def failure_test4_simulate_redis_outage(db: AsyncSession = Depends(get_db)):
    """Simulate Redis outage. Expected: SystemHaltException, fail-closed."""
    shadow_validation_service.set_injection_state("simulate_redis_outage", True)
    logger.warning("failure_test_4_redis_outage_activated")
    return {"test": "simulate_redis_outage", "status": "activated", "expected": "SystemHaltException - Fail-closed behavior"}


@router.post("/failure-injection/test5")
async def failure_test5_simulate_valkey_outage(db: AsyncSession = Depends(get_db)):
    """Simulate Valkey outage. Expected: Fail-closed behavior."""
    shadow_validation_service.set_injection_state("simulate_valkey_outage", True)
    logger.warning("failure_test_5_valkey_outage_activated")
    return {"test": "simulate_valkey_outage", "status": "activated", "expected": "Fail-closed behavior - No trade approval"}


# ── Validation Monitor endpoints ─────────────────────────


@router.get("/monitor/status")
async def get_validation_monitor_status():
    return await shadow_runtime_monitor.get_validation_status()


@router.get("/monitor/latest-snapshot")
async def get_latest_snapshot(db: AsyncSession = Depends(get_db)):
    snap = await shadow_runtime_monitor.get_latest_snapshot(db)
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshots recorded yet")
    return snap


@router.get("/monitor/snapshots")
async def get_snapshot_history(
    limit: int = Query(100, le=500),
    since: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    since_dt = datetime.fromisoformat(since) if since else None
    return await shadow_runtime_monitor.get_snapshot_history(db, limit=limit, since=since_dt)


@router.get("/monitor/alerts")
async def get_active_alerts():
    return {"alerts": shadow_runtime_monitor.get_active_alerts()}
