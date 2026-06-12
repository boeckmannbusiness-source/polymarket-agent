import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet_trade import SolanaWalletTrade as WalletTrade


class WalletTradeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_trade(
        self,
        wallet_id: uuid.UUID,
        tx_signature: str,
        mint_address: str,
        side: str,
        size_usd: float,
        price_usd: float,
        block_time: datetime,
        token_symbol: str | None = None,
        slot: int | None = None,
    ) -> WalletTrade:
        trade = WalletTrade(
            wallet_id=wallet_id,
            tx_signature=tx_signature,
            mint_address=mint_address,
            token_symbol=token_symbol,
            side=side,
            size_usd=size_usd,
            price_usd=price_usd,
            slot=slot,
            block_time=block_time,
        )
        self.db.add(trade)
        await self.db.commit()
        await self.db.refresh(trade)
        return trade

    async def get_by_signature(self, tx_signature: str) -> WalletTrade | None:
        result = await self.db.execute(
            select(WalletTrade).where(WalletTrade.tx_signature == tx_signature),
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, trade_id: uuid.UUID) -> WalletTrade | None:
        result = await self.db.execute(
            select(WalletTrade).where(WalletTrade.id == trade_id),
        )
        return result.scalar_one_or_none()

    async def list_for_wallet(
        self,
        wallet_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[WalletTrade]:
        result = await self.db.execute(
            select(WalletTrade)
            .where(WalletTrade.wallet_id == wallet_id)
            .order_by(WalletTrade.block_time.desc())
            .offset(skip)
            .limit(limit),
        )
        return result.scalars().all()

    async def list_for_mint(
        self,
        mint_address: str,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[WalletTrade]:
        result = await self.db.execute(
            select(WalletTrade)
            .where(WalletTrade.mint_address == mint_address)
            .order_by(WalletTrade.block_time.desc())
            .offset(skip)
            .limit(limit),
        )
        return result.scalars().all()
