import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.metrics import (
    solana_shadow_positions_total,
    solana_shadow_pnl_total,
    solana_shadow_evals_total,
)
from app.models.research_trade import ResearchTrade
from app.models.shadow_position import ShadowPosition
from app.repositories.shadow_position_repository import ShadowPositionRepository
from app.services.shadow_price_service import PriceTrackingService


def _compute_pnl(entry_price: float, exit_price: float, size_usd: float) -> tuple[float, float]:
    quantity = size_usd / entry_price if entry_price > 0 else 0.0
    gross = (exit_price - entry_price) * quantity
    entry_fee = size_usd * settings.SOLANA_SHADOW_FEE_PCT
    exit_fee = size_usd * settings.SOLANA_SHADOW_FEE_PCT
    net = gross - entry_fee - exit_fee
    return round(gross, 2), round(net, 2)


class ShadowPortfolioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ShadowPositionRepository(db)
        self.price_svc = PriceTrackingService(db)

    async def open_from_research_trade(
        self,
        research_trade: ResearchTrade,
        size_usd: float | None = None,
        tp_pct: float | None = None,
        sl_pct: float | None = None,
    ) -> ShadowPosition | None:
        entry_price = float(research_trade.entry_price)
        size = size_usd or entry_price * 100.0
        if size <= 0:
            solana_shadow_evals_total.labels(result="reject_size_zero").inc()
            return None
        if entry_price <= 0:
            solana_shadow_evals_total.labels(result="reject_entry_zero").inc()
            return None

        existing = await self.repo.get_by_research_trade(research_trade.id)
        if existing:
            return existing

        tp_pct = tp_pct or settings.SOLANA_SHADOW_TP_PCT
        sl_pct = sl_pct or settings.SOLANA_SHADOW_SL_PCT

        position = ShadowPosition(
            id=uuid.uuid4(),
            research_trade_id=research_trade.id,
            strategy=research_trade.strategy,
            entry_price=entry_price,
            size_usd=size,
            current_price=entry_price,
            tp_price=entry_price * (1.0 + tp_pct),
            sl_price=entry_price * (1.0 - sl_pct),
            gross_pnl_usd=0.0,
            net_pnl_usd=0.0,
            status="open",
            opened_at=datetime.now(timezone.utc),
        )
        try:
            result = await self.repo.create(position)
        except IntegrityError:
            await self.db.rollback()
            result = await self.repo.get_by_research_trade(research_trade.id)
            if result is None:
                raise
        solana_shadow_positions_total.labels(status="open").inc()
        return result

    async def update_prices(self) -> int:
        open_positions = await self.repo.list_open()
        updated = 0
        for pos in open_positions:
            try:
                price = await self.price_svc.get_price_for_research_trade(pos.research_trade_id)
                if price is not None and price > 0:
                    entry = float(pos.entry_price)
                    size = float(pos.size_usd)
                    gross, net = _compute_pnl(entry, price, size)
                    await self.repo.update_price(pos.id, price, gross, net)
                    solana_shadow_pnl_total.labels(strategy=pos.strategy).set(
                        await self.repo.net_pnl_total_by_strategy(pos.strategy),
                    )
                    updated += 1
            except Exception:
                continue
        return updated

    async def evaluate_all(self) -> list[ShadowPosition]:
        open_positions = await self.repo.list_open()
        closed: list[ShadowPosition] = []
        now = datetime.now(timezone.utc)

        for pos in open_positions:
            current = float(pos.current_price or pos.entry_price)
            entry = float(pos.entry_price)
            size = float(pos.size_usd)
            if entry <= 0:
                continue

            tp = float(pos.tp_price) if pos.tp_price is not None else None
            sl = float(pos.sl_price) if pos.sl_price is not None else None

            exit_price = current
            reason = None

            if tp is not None and current >= tp:
                exit_price = tp
                reason = "take_profit"
            elif sl is not None and current <= sl:
                exit_price = sl
                reason = "stop_loss"
            elif pos.opened_at is not None and (
                now - pos.opened_at.replace(tzinfo=timezone.utc) if pos.opened_at.tzinfo is None else now - pos.opened_at
            ).total_seconds() > settings.SOLANA_SHADOW_TIMEOUT_HOURS * 3600:
                reason = "timeout"

            if reason:
                gross, net = _compute_pnl(entry, exit_price, size)
                result = await self.repo.close_position(
                    pos.id, exit_price, gross, net, reason,
                )
                if result:
                    closed.append(result)
                    solana_shadow_positions_total.labels(status="open").dec()
                    solana_shadow_positions_total.labels(status="closed").inc()
                    solana_shadow_evals_total.labels(result=reason).inc()
            else:
                solana_shadow_evals_total.labels(result="held").inc()
        return closed

    async def close_position(
        self,
        position_id: uuid.UUID,
        reason: str = "manual",
    ) -> ShadowPosition | None:
        pos = await self.repo.get_by_id(position_id)
        if not pos or pos.status != "open":
            return None
        exit_price = float(pos.current_price or pos.entry_price)
        entry = float(pos.entry_price)
        size = float(pos.size_usd)
        gross, net = _compute_pnl(entry, exit_price, size)
        result = await self.repo.close_position(
            pos.id, exit_price, gross, net, reason,
        )
        if result:
            solana_shadow_positions_total.labels(status="open").dec()
            solana_shadow_positions_total.labels(status="closed").inc()
            solana_shadow_evals_total.labels(result=f"closed_{reason}").inc()
        return result
