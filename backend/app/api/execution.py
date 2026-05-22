from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.strategies import get_strategy, get_strategy_names, list_strategies
from app.services.safety_service import SafetyService
from app.services.regime_service import RegimeService
from app.services.execution_simulator import ExecutionSimulator, OrderSide, OrderbookSnapshot
from app.services.strategy_service import StrategyService
from app.replay.feature_schemas import get_feature_schema, list_feature_versions, validate_features

router = APIRouter()


@router.get("/simulate/slippage")
async def estimate_slippage(
    size: float = Query(gt=0),
    liquidity: float = Query(gt=0),
    mid_price: float = Query(default=0.5, gt=0, le=1),
):
    sim = ExecutionSimulator()
    slippage = sim.estimate_slippage(size, liquidity, mid_price)
    fill = sim.simulate_market_order(
        OrderSide.BUY, size,
        mid_price=mid_price, liquidity=liquidity,
    )
    return {
        "estimated_slippage": round(slippage, 6),
        "simulated_fill": {
            "filled_size": fill.filled_size,
            "avg_fill_price": round(fill.avg_fill_price, 6),
            "slippage": round(fill.slippage, 6),
            "spread_cost": round(fill.spread_cost, 6),
            "partial": fill.partial,
            "remaining_size": fill.remaining_size,
            "fill_events": fill.fill_events[:3],
        },
    }


@router.post("/simulate/order")
async def simulate_order(
    side: str = Query(pattern="^(BUY|SELL)$"),
    size: float = Query(gt=0),
    mid_price: float = Query(default=0.5, gt=0, le=1),
    liquidity: float = Query(default=10000.0, gt=0),
    latency_ms: float = Query(default=50.0, ge=0),
):
    sim = ExecutionSimulator(latency_ms=latency_ms)
    orderbook = OrderbookSnapshot.from_liquidity(mid_price, liquidity)
    result = sim.simulate_market_order(
        OrderSide[side],
        size,
        orderbook=orderbook,
    )
    return {
        "side": side,
        "requested_size": size,
        "filled_size": result.filled_size,
        "avg_fill_price": round(result.avg_fill_price, 6),
        "slippage": round(result.slippage, 6),
        "spread_cost": round(result.spread_cost, 6),
        "partial_fill": result.partial,
        "remaining_size": result.remaining_size,
        "queue_position": round(result.queue_position, 4),
        "fill_events": result.fill_events,
        "orderbook": {
            "mid_price": orderbook.mid_price,
            "spread": orderbook.spread,
            "bid_depth": sum(b.price * b.size for b in orderbook.bids),
            "ask_depth": sum(a.price * a.size for a in orderbook.asks),
        },
    }


@router.get("/features/schemas")
async def list_feature_schemas():
    versions = list_feature_versions()
    return {
        "versions": versions,
        "current": versions[-1] if versions else None,
    }


@router.get("/features/schemas/{version}")
async def get_feature_schema_detail(version: str):
    try:
        schema = get_feature_schema(version)
        return schema
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/features/validate")
async def validate_feature_data(features: dict, schema_version: str = "1.0.0"):
    errors = validate_features(features, schema_version)
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "feature_count": len(features),
    }


@router.get("/strategies/lifecycle")
async def get_strategy_lifecycles(db: AsyncSession = Depends(get_db)):
    service = StrategyService(db)
    names = get_strategy_names()
    result = []
    for name in names:
        config_row = await service.get_config(name)
        try:
            strategy = get_strategy(name)
            meta = strategy.get_metadata()
        except ValueError:
            meta = {"name": name}
        result.append({
            "name": name,
            "lifecycle": config_row.lifecycle if config_row and hasattr(config_row, "lifecycle") else "ACTIVE",
            "enabled": config_row.enabled if config_row else True,
            "version": config_row.version if config_row else meta.get("version", "1.0.0"),
        })
    return result


@router.put("/strategies/{strategy_name}/lifecycle")
async def set_strategy_lifecycle(
    strategy_name: str,
    lifecycle: str = Query(pattern="^(ACTIVE|SHADOW|EXPERIMENTAL|DEPRECATED)$"),
    db: AsyncSession = Depends(get_db),
):
    try:
        get_strategy(strategy_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    service = StrategyService(db)
    config_row = await service.get_config(strategy_name)
    if config_row:
        config_row.lifecycle = lifecycle
    else:
        config_row = await service.save_config(strategy_name, {}, version="1.0.0")
        config_row.lifecycle = lifecycle

    await db.commit()
    return {"strategy": strategy_name, "lifecycle": lifecycle}


@router.get("/regimes")
async def get_current_regimes(
    market_condition_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = RegimeService(db)
    probs = await service.classify(market_condition_id)
    return probs.to_dict()


@router.get("/safety/status")
async def get_safety_status(db: AsyncSession = Depends(get_db)):
    service = SafetyService(db)
    return await service.get_state()


@router.post("/safety/kill-switch")
async def toggle_kill_switch(
    active: bool = Query(),
    reason: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    service = SafetyService(db)
    await service.set_kill_switch(active, reason)
    await db.commit()
    return {"kill_switch_active": active, "reason": reason}


@router.post("/safety/quarantine/{strategy_name}")
async def toggle_strategy_quarantine(
    strategy_name: str,
    quarantine: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
):
    service = SafetyService(db)
    await service.quarantine_strategy(strategy_name, quarantine)
    await db.commit()
    return {"strategy": strategy_name, "quarantined": quarantine}


@router.post("/safety/check-trade")
async def check_trade_approval(
    strategy_name: str,
    size: float = Query(gt=0),
    confidence: float = Query(default=0.5, ge=0, le=1),
    db: AsyncSession = Depends(get_db),
):
    service = SafetyService(db)
    result = await service.check_trade_approval(strategy_name, size, confidence)
    await db.commit()
    return {
        "approved": result.approved,
        "reasons": result.reasons,
        "circuit_breaker": result.circuit_breaker.value if result.circuit_breaker else None,
    }
