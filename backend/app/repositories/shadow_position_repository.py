import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_position import ShadowPosition


class ShadowPositionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, position: ShadowPosition) -> ShadowPosition:
        self.db.add(position)
        await self.db.commit()
        await self.db.refresh(position)
        return position

    async def get_by_id(self, position_id: uuid.UUID) -> ShadowPosition | None:
        result = await self.db.execute(
            select(ShadowPosition).where(ShadowPosition.id == position_id),
        )
        return result.scalar_one_or_none()

    async def get_by_research_trade(self, research_trade_id: uuid.UUID) -> ShadowPosition | None:
        result = await self.db.execute(
            select(ShadowPosition).where(ShadowPosition.research_trade_id == research_trade_id),
        )
        return result.scalar_one_or_none()

    async def list_open(self) -> Sequence[ShadowPosition]:
        result = await self.db.execute(
            select(ShadowPosition)
            .where(ShadowPosition.status == "open")
            .order_by(ShadowPosition.opened_at.desc()),
        )
        return result.scalars().all()

    async def list_by_strategy(self, strategy: str) -> Sequence[ShadowPosition]:
        result = await self.db.execute(
            select(ShadowPosition)
            .where(ShadowPosition.strategy == strategy)
            .order_by(ShadowPosition.opened_at.desc()),
        )
        return result.scalars().all()

    async def close_position(
        self,
        position_id: uuid.UUID,
        exit_price: float,
        gross_pnl_usd: float,
        net_pnl_usd: float,
        close_reason: str,
    ) -> ShadowPosition | None:
        now = datetime.now().astimezone()
        await self.db.execute(
            update(ShadowPosition)
            .where(ShadowPosition.id == position_id)
            .values(
                exit_price=exit_price,
                current_price=exit_price,
                gross_pnl_usd=gross_pnl_usd,
                net_pnl_usd=net_pnl_usd,
                status="closed",
                closed_at=now,
                close_reason=close_reason,
            ),
        )
        await self.db.commit()
        return await self.get_by_id(position_id)

    async def update_current_price(
        self, position_id: uuid.UUID, current_price: float,
    ) -> ShadowPosition | None:
        await self.db.execute(
            update(ShadowPosition)
            .where(ShadowPosition.id == position_id)
            .values(current_price=current_price),
        )
        await self.db.commit()
        return await self.get_by_id(position_id)

    async def update_price(
        self, position_id: uuid.UUID, current_price: float, gross_pnl_usd: float, net_pnl_usd: float,
    ) -> ShadowPosition | None:
        await self.db.execute(
            update(ShadowPosition)
            .where(ShadowPosition.id == position_id)
            .values(
                current_price=current_price,
                gross_pnl_usd=gross_pnl_usd,
                net_pnl_usd=net_pnl_usd,
            ),
        )
        await self.db.commit()
        return await self.get_by_id(position_id)

    async def count_by_status(self, status: str) -> int:
        result = await self.db.execute(
            select(ShadowPosition).where(ShadowPosition.status == status).with_only_columns(ShadowPosition.id),
        )
        return len(result.all())

    async def net_pnl_total_by_strategy(self, strategy: str) -> float:
        result = await self.db.execute(
            select(ShadowPosition.net_pnl_usd).where(
                ShadowPosition.strategy == strategy,
                ShadowPosition.status == "open",
                ShadowPosition.net_pnl_usd.isnot(None),
            ),
        )
        rows = result.all()
        return sum(float(r.net_pnl_usd) for r in rows if r.net_pnl_usd is not None)
