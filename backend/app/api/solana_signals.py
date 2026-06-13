from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.research_trade import ResearchTrade
from app.repositories.research_trade_repository import ResearchTradeRepository

router = APIRouter()


class SolanaSignalResponse(BaseModel):
    id: UUID
    signal_id: str | None
    strategy: str
    entry_price: float
    confidence: float | None
    status: str
    opened_at: str
    created_at: str | None = None

    model_config = {"from_attributes": True}


def _to_response(t: ResearchTrade) -> SolanaSignalResponse:
    return SolanaSignalResponse(
        id=t.id,
        signal_id=t.signal_id,
        strategy=t.strategy,
        entry_price=float(t.entry_price) if t.entry_price is not None else 0.0,
        confidence=float(t.confidence) if t.confidence is not None else None,
        status=t.status,
        opened_at=t.opened_at.isoformat() if t.opened_at else "",
        created_at=t.created_at.isoformat() if t.created_at else None,
    )


@router.get("")
async def list_solana_signals(
    skip: int = 0,
    limit: int = 50,
    strategy: str | None = Query(None),
    status: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> list[SolanaSignalResponse]:
    repo = ResearchTradeRepository(db)
    if status == "open":
        trades = await repo.list_open_positions(strategy=strategy, skip=skip, limit=limit)
    else:
        trades = await repo.list_by_strategy(strategy or "", skip=skip, limit=limit)
        if strategy:
            trades = await repo.list_by_strategy(strategy, skip=skip, limit=limit)
    return [_to_response(t) for t in trades]


@router.get("/{signal_id}")
async def get_solana_signal(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SolanaSignalResponse:
    repo = ResearchTradeRepository(db)
    trade = await repo.get_by_id(signal_id)
    return _to_response(trade)
