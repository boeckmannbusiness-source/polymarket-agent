from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.wallet import WalletResponse, WalletDetailResponse, WalletScoreResponse
from app.services.whale_service import WhaleService

router = APIRouter()


@router.get("")
async def list_wallets(
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "realized_pnl",
    db: AsyncSession = Depends(get_db),
) -> list[WalletResponse]:
    service = WhaleService(db)
    return await service.list_wallets(skip=skip, limit=limit, sort_by=sort_by)


@router.get("/{address}")
async def get_wallet(
    address: str,
    db: AsyncSession = Depends(get_db),
) -> WalletDetailResponse:
    service = WhaleService(db)
    return await service.get_wallet(address)


@router.get("/{address}/scores")
async def get_wallet_scores(
    address: str,
    score_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[WalletScoreResponse]:
    service = WhaleService(db)
    return await service.get_wallet_scores(address, score_type=score_type)


@router.get("/leaderboard/top")
async def get_leaderboard(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[WalletResponse]:
    service = WhaleService(db)
    return await service.get_leaderboard(limit=limit)
