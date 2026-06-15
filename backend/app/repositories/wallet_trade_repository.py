import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.smart_wallet import SmartWallet
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

    async def list_for_mint_since(
        self,
        mint_address: str,
        since: datetime,
        limit: int = 100,
    ) -> Sequence[WalletTrade]:
        result = await self.db.execute(
            select(WalletTrade)
            .where(WalletTrade.mint_address == mint_address)
            .where(WalletTrade.block_time >= since)
            .order_by(WalletTrade.block_time.desc())
            .limit(limit),
        )
        return result.scalars().all()

    async def aggregate_wallet_metrics(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)
        seven_days_ago = now - timedelta(hours=168)

        result = await self.db.execute(
            select(
                SmartWallet.wallet_address,
                func.count().label("trades_total"),
                func.sum(case((WalletTrade.block_time >= one_hour_ago, 1), else_=0)).label("trades_1h"),
                func.sum(case((WalletTrade.block_time >= one_day_ago, 1), else_=0)).label("trades_24h"),
                func.sum(case((WalletTrade.block_time >= seven_days_ago, 1), else_=0)).label("trades_7d"),
                func.count(func.distinct(WalletTrade.mint_address)).label("token_diversity"),
                func.sum(case((WalletTrade.price_usd > 0, WalletTrade.size_usd), else_=0)).label("volume_proxy"),
                func.count(func.distinct(func.date(WalletTrade.block_time))).label("active_days_7d"),
                func.max(WalletTrade.block_time).label("last_trade_at"),
            )
            .join(SmartWallet, WalletTrade.wallet_id == SmartWallet.id)
            .group_by(SmartWallet.wallet_address)
        )
        rows = result.all()
        return [
            {
                "wallet_address": row.wallet_address,
                "trades_1h": row.trades_1h or 0,
                "trades_24h": row.trades_24h or 0,
                "trades_7d": row.trades_7d or 0,
                "token_diversity": row.token_diversity or 0,
                "volume_proxy": float(row.volume_proxy) if row.volume_proxy else 0.0,
                "active_days_7d": row.active_days_7d or 0,
                "last_trade_at": row.last_trade_at.isoformat() if row.last_trade_at else None,
            }
            for row in rows
        ]
