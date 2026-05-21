from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.signal import SignalResponse
from app.services.signal_service import SignalService

router = APIRouter()


@router.get("")
async def list_signals(
    skip: int = 0,
    limit: int = 50,
    is_active: bool | None = Query(None),
    signal_type: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
) -> list[SignalResponse]:
    service = SignalService(db)
    return await service.list_signals(
        skip=skip,
        limit=limit,
        is_active=is_active,
        signal_type=signal_type,
        min_confidence=min_confidence,
    )


@router.get("/{signal_id}")
async def get_signal(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SignalResponse:
    service = SignalService(db)
    return await service.get_signal(signal_id)
