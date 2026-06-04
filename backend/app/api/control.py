from fastapi import APIRouter, HTTPException

from app.services.control.control_plane import control_plane

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
