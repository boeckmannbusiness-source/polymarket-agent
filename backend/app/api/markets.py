from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.market import MarketResponse, MarketDetailResponse, MarketEventResponse
from app.services.market_service import MarketService

router = APIRouter()


@router.get("")
async def list_markets(
    skip: int = 0,
    limit: int = 50,
    resolved: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[MarketResponse]:
    service = MarketService(db)
    return await service.list_markets(skip=skip, limit=limit, resolved=resolved)


@router.get("/{market_id}")
async def get_market(
    market_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MarketDetailResponse:
    service = MarketService(db)
    return await service.get_market(market_id)


@router.get("/{market_id}/events")
async def get_market_events(
    market_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[MarketEventResponse]:
    service = MarketService(db)
    return await service.get_market_events(market_id, skip=skip, limit=limit)


@router.get("/slug/{slug}")
async def get_market_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> MarketDetailResponse:
    service = MarketService(db)
    return await service.get_market_by_slug(slug)
