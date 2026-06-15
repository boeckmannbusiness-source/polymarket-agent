import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.research_trade import ResearchTrade
from app.models.wallet_trade import SolanaWalletTrade
from app.models.smart_wallet import SmartWallet


_WALLET_LOADS = [
    selectinload(ResearchTrade.wallet_trade).selectinload(SolanaWalletTrade.wallet),
]


class ResearchTradeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_trade(
        self,
        strategy: str,
        entry_price: float,
        opened_at: datetime,
        signal_id: str | None = None,
        wallet_trade_id: uuid.UUID | None = None,
        confidence: float | None = None,
    ) -> ResearchTrade:
        trade = ResearchTrade(
            signal_id=signal_id,
            wallet_trade_id=wallet_trade_id,
            strategy=strategy,
            confidence=confidence,
            entry_price=entry_price,
            opened_at=opened_at,
        )
        self.db.add(trade)
        await self.db.commit()
        await self.db.refresh(trade)
        return trade

    async def get_by_id(self, trade_id: uuid.UUID) -> ResearchTrade | None:
        result = await self.db.execute(
            select(ResearchTrade)
            .options(*_WALLET_LOADS)
            .where(ResearchTrade.id == trade_id),
        )
        return result.scalar_one_or_none()

    async def close_trade(
        self,
        trade_id: uuid.UUID,
        exit_price: float,
        pnl_usd: float,
        closed_at: datetime | None = None,
    ) -> ResearchTrade | None:
        now = closed_at or datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.execute(
            update(ResearchTrade)
            .where(ResearchTrade.id == trade_id)
            .values(
                exit_price=exit_price,
                pnl_usd=pnl_usd,
                status="closed",
                closed_at=now,
            ),
        )
        await self.db.commit()
        return await self.get_by_id(trade_id)

    async def list_open_positions(
        self,
        strategy: str | None = None,
        skip: int = 0,
        limit: int | None = 100,
    ) -> Sequence[ResearchTrade]:
        query = (
            select(ResearchTrade)
            .options(*_WALLET_LOADS)
            .where(ResearchTrade.status == "open")
        )
        if strategy:
            query = query.where(ResearchTrade.strategy == strategy)
        query = query.order_by(ResearchTrade.opened_at.desc()).offset(skip)
        if limit is not None:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def list_all(
        self,
        skip: int = 0,
        limit: int | None = 100,
    ) -> Sequence[ResearchTrade]:
        query = (
            select(ResearchTrade)
            .options(*_WALLET_LOADS)
            .order_by(ResearchTrade.opened_at.desc())
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def list_by_strategy(
        self,
        strategy: str,
        skip: int = 0,
        limit: int | None = 100,
    ) -> Sequence[ResearchTrade]:
        query = (
            select(ResearchTrade)
            .options(*_WALLET_LOADS)
            .where(ResearchTrade.strategy == strategy)
            .order_by(ResearchTrade.opened_at.desc())
            .offset(skip)
        )
        if limit is not None:
            query = query.limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_open(self) -> int:
        result = await self.db.execute(
            select(ResearchTrade).where(ResearchTrade.status == "open").with_only_columns(ResearchTrade.id),
        )
        return len(result.all())
