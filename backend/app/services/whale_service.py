from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, desc, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Wallet, WalletTrade, WalletScore, WalletCluster
from app.core.exceptions import WalletNotFoundError


class WhaleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_wallets(
        self,
        skip: int = 0,
        limit: int = 50,
        sort_by: str = "realized_pnl",
    ) -> list[Wallet]:
        allowed_sorts = {"realized_pnl", "total_volume", "total_trades", "win_rate", "current_rank"}
        sort_col = getattr(Wallet, sort_by if sort_by in allowed_sorts else "realized_pnl")
        query = select(Wallet).order_by(desc(sort_col)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_wallet(self, address: str) -> Wallet:
        result = await self.db.execute(select(Wallet).where(Wallet.address == address))
        wallet = result.scalar_one_or_none()
        if not wallet:
            raise WalletNotFoundError(f"Wallet {address} not found")
        return wallet

    async def get_wallet_scores(self, address: str, score_type: str | None = None) -> list[WalletScore]:
        query = select(WalletScore).where(WalletScore.wallet_address == address)
        if score_type:
            query = query.where(WalletScore.score_type == score_type)
        query = query.order_by(desc(WalletScore.calculated_at))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_leaderboard(self, limit: int = 20) -> list[Wallet]:
        query = select(Wallet).order_by(desc(Wallet.realized_pnl)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def upsert_wallet(self, address: str, **kwargs) -> Wallet:
        result = await self.db.execute(select(Wallet).where(Wallet.address == address))
        wallet = result.scalar_one_or_none()
        if wallet:
            for key, value in kwargs.items():
                if value is not None:
                    setattr(wallet, key, value)
            wallet.last_seen = datetime.now(timezone.utc)
        else:
            wallet = Wallet(
                address=address,
                first_seen=datetime.now(timezone.utc),
                last_seen=datetime.now(timezone.utc),
                **{k: v for k, v in kwargs.items() if v is not None},
            )
            self.db.add(wallet)
        await self.db.flush()
        return wallet

    async def record_trade(self, wallet_address: str, **kwargs) -> WalletTrade:
        trade = WalletTrade(wallet_address=wallet_address, **kwargs)
        self.db.add(trade)
        wallet = await self.get_wallet(wallet_address)
        wallet.total_trades += 1
        if kwargs.get("size"):
            wallet.total_volume = float(wallet.total_volume or 0) + float(kwargs["size"])
        if kwargs.get("pnl") is not None:
            pnl_val = float(kwargs["pnl"])
            wallet.realized_pnl = float(wallet.realized_pnl or 0) + pnl_val
            if pnl_val > 0:
                wallet.win_count += 1
            else:
                wallet.loss_count += 1
            total = wallet.win_count + wallet.loss_count
            wallet.win_rate = round(wallet.win_count / total, 6) if total > 0 else None
        await self.db.flush()
        return trade

    async def calculate_scores(self, wallet_address: str):
        """Recalculate all scores for a wallet."""
        wallet = await self.get_wallet(wallet_address)
        trades_result = await self.db.execute(
            select(WalletTrade).where(
                and_(
                    WalletTrade.wallet_address == wallet_address,
                    WalletTrade.is_open == False,
                    WalletTrade.pnl.isnot(None),
                )
            )
        )
        trades = list(trades_result.scalars().all())

        if not trades:
            return

        pnls = [float(t.pnl) for t in trades if t.pnl is not None]
        volumes = [float(t.size or 0) for t in trades]

        overall_score = sum(pnls) / len(pnls) if pnls else 0
        total_volume = sum(volumes)
        recent_pnls = pnls[-20:] if len(pnls) > 20 else pnls
        momentum_score = sum(recent_pnls) / len(recent_pnls) if recent_pnls else 0

        now = datetime.now(timezone.utc)

        scores = [
            WalletScore(
                wallet_address=wallet_address,
                score_type="overall",
                score=overall_score,
                confidence=min(len(pnls) / 100, 1.0),
                period_end=now,
            ),
            WalletScore(
                wallet_address=wallet_address,
                score_type="momentum",
                score=momentum_score,
                confidence=min(len(recent_pnls) / 20, 1.0),
                period_end=now,
            ),
        ]

        for score in scores:
            self.db.add(score)

        await self.db.flush()
