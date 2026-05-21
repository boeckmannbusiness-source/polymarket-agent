from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.trade import TradeResponse, TradeCreateRequest
from app.services.trade_service import TradeService

router = APIRouter()


@router.get("")
async def list_trades(
    skip: int = 0,
    limit: int = 50,
    status: str | None = Query(None),
    trade_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[TradeResponse]:
    service = TradeService(db)
    return await service.list_trades(
        skip=skip, limit=limit, status=status, trade_type=trade_type
    )


@router.get("/{trade_id}")
async def get_trade(
    trade_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    service = TradeService(db)
    return await service.get_trade(trade_id)


@router.post("")
async def create_trade(
    request: TradeCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    service = TradeService(db)
    return await service.create_trade(request)


@router.post("/{trade_id}/close")
async def close_trade(
    trade_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> TradeResponse:
    service = TradeService(db)
    return await service.close_trade(trade_id)


@router.post("/emergency-stop")
async def emergency_stop(db: AsyncSession = Depends(get_db)):
    service = TradeService(db)
    await service.emergency_stop()
    return {"status": "stopped", "message": "All trading halted"}
