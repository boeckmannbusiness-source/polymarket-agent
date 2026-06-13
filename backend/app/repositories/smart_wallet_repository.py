import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.smart_wallet import SmartWallet


class SmartWalletRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_wallet(
        self,
        wallet_address: str,
        source: str = "helius",
        label: str | None = None,
        first_seen_at: datetime | None = None,
    ) -> SmartWallet:
        now = first_seen_at or datetime.now(timezone.utc).replace(tzinfo=None)
        wallet = SmartWallet(
            wallet_address=wallet_address,
            source=source,
            label=label,
            first_seen_at=now,
        )
        self.db.add(wallet)
        await self.db.commit()
        await self.db.refresh(wallet)
        return wallet

    async def get_by_address(self, wallet_address: str) -> SmartWallet | None:
        result = await self.db.execute(
            select(SmartWallet).where(SmartWallet.wallet_address == wallet_address),
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, wallet_id: uuid.UUID) -> SmartWallet | None:
        result = await self.db.execute(
            select(SmartWallet).where(SmartWallet.id == wallet_id),
        )
        return result.scalar_one_or_none()

    async def update_metrics(
        self,
        wallet_id: uuid.UUID,
        total_trades: int | None = None,
        win_rate: float | None = None,
        pnl_usd: float | None = None,
        score: float | None = None,
        last_seen_at: datetime | None = None,
    ) -> SmartWallet | None:
        values: dict = {}
        if total_trades is not None:
            values["total_trades"] = total_trades
        if win_rate is not None:
            values["win_rate"] = win_rate
        if pnl_usd is not None:
            values["pnl_usd"] = pnl_usd
        if score is not None:
            values["score"] = score
        if last_seen_at is not None:
            values["last_seen_at"] = last_seen_at

        if not values:
            return await self.get_by_id(wallet_id)

        await self.db.execute(
            update(SmartWallet).where(SmartWallet.id == wallet_id).values(**values),
        )
        await self.db.commit()
        return await self.get_by_id(wallet_id)

    async def list_active(self, skip: int = 0, limit: int = 100) -> Sequence[SmartWallet]:
        result = await self.db.execute(
            select(SmartWallet)
            .where(SmartWallet.is_active == True)
            .order_by(SmartWallet.score.desc())
            .offset(skip)
            .limit(limit),
        )
        return result.scalars().all()

    async def upsert_wallet(
        self,
        wallet_address: str,
        source: str = "helius",
        label: str | None = None,
        score: float | None = None,
    ) -> SmartWallet:
        existing = await self.get_by_address(wallet_address)
        if existing:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            values: dict = {"last_seen_at": now}
            if label is not None:
                values["label"] = label
            if score is not None:
                values["score"] = score
            await self.db.execute(
                update(SmartWallet).where(SmartWallet.id == existing.id).values(**values),
            )
            await self.db.commit()
            return await self.get_by_id(existing.id)
        return await self.create_wallet(
            wallet_address=wallet_address,
            source=source,
            label=label,
        )
