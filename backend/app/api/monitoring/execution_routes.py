from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.monitoring.execution_metrics_service import ExecutionMetricsService
from app.services.monitoring.pnl_service import PnLService
from app.services.monitoring.order_state_service import OrderStateService
from app.services.monitoring.drift_service import DriftDetectionService

router = APIRouter()


@router.get("/trades/{trade_id}")
async def get_trade_monitoring(trade_id: UUID, db: AsyncSession = Depends(get_db)):
    metrics = ExecutionMetricsService(db)
    state = OrderStateService(db)
    trade_metrics = await metrics.get_trade_metrics(trade_id)
    orders = await state.get_trade_orders(trade_id)
    return {
        "metrics": trade_metrics,
        "orders": [vars(o) for o in orders],
    }


@router.get("/orders/{order_id}")
async def get_order_monitoring(order_id: UUID, db: AsyncSession = Depends(get_db)):
    state = OrderStateService(db)
    view = await state.get_order_view(order_id)
    if not view:
        raise HTTPException(status_code=404, detail="Order not found")
    drift = DriftDetectionService(db)
    from app.models import ExchangeOrder
    result = await db.execute(
        __import__("sqlalchemy").select(ExchangeOrder).where(ExchangeOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    drift_report = await drift.detect_order_drift(order) if order else {"drift_detected": False, "issues": []}
    return {
        "order": vars(view),
        "drift": drift_report,
    }


@router.get("/positions/{market_id}")
async def get_position_monitoring(market_id: UUID, db: AsyncSession = Depends(get_db)):
    metrics = ExecutionMetricsService(db)
    from app.models import Position
    result = await db.execute(
        __import__("sqlalchemy").select(Position).where(
            Position.market_id == market_id,
            Position.status == "OPEN",
        )
    )
    position = result.scalar_one_or_none()
    market_metrics = await metrics.get_market_metrics(market_id)
    drift = DriftDetectionService(db)
    drift_report = await drift.detect_position_drift(position) if position else {"drift_detected": False, "issues": [], "position_id": str(market_id)}
    return {
        "market_metrics": market_metrics,
        "position": {
            "id": str(position.id),
            "direction": position.direction,
            "size": float(position.size),
            "entry_price": float(position.entry_price),
            "current_price": float(position.current_price) if position.current_price else None,
            "unrealized_pnl": float(position.unrealized_pnl) if position.unrealized_pnl else 0,
            "realized_pnl": float(position.realized_pnl) if position.realized_pnl else 0,
            "status": position.status,
        } if position else None,
        "drift": drift_report,
    }


@router.get("/portfolio")
async def get_portfolio_monitoring(db: AsyncSession = Depends(get_db)):
    pnl = PnLService(db)
    state = OrderStateService(db)
    active_orders = await state.get_active_orders()
    portfolio_pnl = await pnl.get_portfolio_pnl()
    return {
        "pnl": portfolio_pnl,
        "active_orders_count": len(active_orders),
        "active_orders": [vars(o) for o in active_orders[:20]],
    }


@router.get("/strategy/{agent_id}")
async def get_strategy_monitoring(agent_id: str, db: AsyncSession = Depends(get_db)):
    metrics = ExecutionMetricsService(db)
    strategy_metrics = await metrics.get_strategy_metrics(agent_id)
    return {
        "strategy_metrics": strategy_metrics,
    }
