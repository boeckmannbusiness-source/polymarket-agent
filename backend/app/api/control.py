from fastapi import APIRouter, HTTPException

from app.services.control.control_plane import control_plane
from app.services.control.autonomous_control_pipeline import autonomous_control_pipeline
from app.services.control.stability_controller_service import stability_controller
from app.services.control.portfolio_drift_detector import portfolio_drift_detector
from app.services.control.regime_transition_controller import regime_transition_controller
from app.schemas.control import PortfolioControlReport
from app.core.metrics import portfolio_stability_score, allocation_drift_events

router = APIRouter()


@router.get("/state")
async def control_state():
    return await control_plane.get_state()


@router.post("/trading/enable")
async def enable_trading():
    await control_plane.set_trading_enabled(True)
    return {"trading_enabled": True}


@router.post("/trading/disable")
async def disable_trading():
    await control_plane.set_trading_enabled(False)
    return {"trading_enabled": False}


@router.post("/strategy/{strategy_id}/pause")
async def pause_strategy(strategy_id: str):
    await control_plane.pause_strategy(strategy_id)
    return {"strategy_id": strategy_id, "paused": True}


@router.post("/strategy/{strategy_id}/resume")
async def resume_strategy(strategy_id: str):
    await control_plane.resume_strategy(strategy_id)
    return {"strategy_id": strategy_id, "paused": False}


@router.get("/strategies/paused")
async def paused_strategies():
    return {"paused": await control_plane.get_paused_strategies()}


@router.post("/market/{market_id}/pause")
async def pause_market(market_id: str):
    await control_plane.pause_market(market_id)
    return {"market_id": market_id, "paused": True}


@router.post("/market/{market_id}/resume")
async def resume_market(market_id: str):
    await control_plane.resume_market(market_id)
    return {"market_id": market_id, "paused": False}


@router.post("/execution-mode/{mode}")
async def set_execution_mode(mode: str):
    if mode not in ("paper", "live", "shadow"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    await control_plane.set_execution_mode(mode)
    return {"execution_mode": mode}


# ── Phase 4G: Portfolio Control ──────────────────────────


@router.get("/portfolio/state")
async def portfolio_state():
    result = await autonomous_control_pipeline.get_latest()
    if result is None:
        raise HTTPException(status_code=404, detail="No portfolio state available")
    return result


@router.get("/portfolio/drift")
async def portfolio_drift():
    drift = await portfolio_drift_detector.get_latest()
    if drift is None:
        raise HTTPException(status_code=404, detail="No drift data available")
    return drift


@router.get("/portfolio/stability")
async def portfolio_stability():
    state = await autonomous_control_pipeline.get_latest()
    if state is None:
        raise HTTPException(status_code=404, detail="No stability data available")
    return {
        "allocation_stability": 100.0 - state.stability.total_turnover_pct if state.stability else 100.0,
        "turnover_rate": state.stability.total_turnover_pct / 100.0 if state.stability else 0.0,
        "drift_index": state.drift.overall_drift_score if state.drift else 0,
        "regime_stability": any(r.transitions_smoothed for r in state.regime_transitions.regimes) if state.regime_transitions else False,
    }


@router.post("/portfolio/run")
async def portfolio_run():
    report = await autonomous_control_pipeline.run()
    allocation_drift_events.inc(max(0, report.drift_report.drift_score // 10))
    portfolio_stability_score.set(report.stability_adjustment.allocation_stability)
    return report
