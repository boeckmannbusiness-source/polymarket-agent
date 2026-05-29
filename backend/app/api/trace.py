from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AgentLog, Signal, Trade, ExecutionTrace

router = APIRouter()


@router.get("/trace/{correlation_id}")
async def get_trace(correlation_id: UUID, db: AsyncSession = Depends(get_db)):
    agent_logs = await db.execute(
        select(AgentLog).where(AgentLog.correlation_id == correlation_id)
        .order_by(AgentLog.timestamp)
    )
    signals = await db.execute(
        select(Signal).where(Signal.correlation_id == correlation_id)
    )
    trades = await db.execute(
        select(Trade).where(Trade.correlation_id == correlation_id)
    )
    traces = await db.execute(
        select(ExecutionTrace).where(ExecutionTrace.correlation_id == correlation_id)
    )

    def serialize_log(log):
        return {"type": "agent_log", "id": str(log.id), "agent": log.agent_name, "event": log.event_type, "data": log.data, "timestamp": log.timestamp.isoformat() if log.timestamp else None}

    def serialize_signal(sig):
        return {"type": "signal", "id": str(sig.id), "signal_type": sig.signal_type, "direction": sig.direction, "confidence": float(sig.confidence), "timestamp": sig.generated_at.isoformat() if sig.generated_at else None}

    def serialize_trade(t):
        return {"type": "trade", "id": str(t.id), "market_id": str(t.market_id) if t.market_id else None, "status": t.status, "side": t.side, "outcome": t.outcome, "size": float(t.size) if t.size else None, "filled_price": float(t.filled_price) if t.filled_price else None, "timestamp": t.created_at.isoformat() if t.created_at else None}

    def serialize_trace(tr):
        return {"type": "execution_trace", "id": str(tr.id), "trade_id": str(tr.trade_id) if tr.trade_id else None, "risk_approved": tr.risk_approved, "fill_status": tr.fill_status, "strategy": tr.strategy_name, "timestamp": tr.created_at.isoformat() if tr.created_at else None}

    events = sorted(
        [serialize_log(log) for log in agent_logs.scalars().all()] +
        [serialize_signal(sig) for sig in signals.scalars().all()] +
        [serialize_trade(t) for t in trades.scalars().all()] +
        [serialize_trace(tr) for tr in traces.scalars().all()],
        key=lambda e: e["timestamp"] or ""
    )

    return {
        "correlation_id": str(correlation_id),
        "timeline": events,
        "span_count": len(events),
        "trade_ids": [str(t.id) for t in trades.scalars().all()],
        "signal_ids": [str(s.id) for s in signals.scalars().all()],
    }
