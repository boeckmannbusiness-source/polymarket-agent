from uuid import UUID
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, Signal
from app.core.exceptions import RiskLimitReachedError


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str | None = None
    max_position_size: float | None = None
    max_daily_loss: float | None = None
    max_open_positions: int | None = None
    cooldown_remaining: int | None = None


VALID_SIDES = {"buy", "sell"}


class RiskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_trade(
        self,
        market_id: UUID | None,
        side: str,
        size: float | None,
        confidence: float | None,
        agent_id: str | None = None,
    ) -> RiskCheckResult:
        if market_id is None:
            return RiskCheckResult(approved=False, reason="market_id is required")
        if side not in VALID_SIDES:
            return RiskCheckResult(approved=False, reason=f"Invalid side: {side}")
        if size is None or size <= 0:
            return RiskCheckResult(approved=False, reason=f"Invalid size: {size}")

        if confidence is None:
            confidence = 0.0
        min_confidence = getattr(settings, "MIN_CONFIDENCE_THRESHOLD", 0.6)
        if confidence < min_confidence:
            return RiskCheckResult(
                approved=False,
                reason=f"Confidence {confidence:.2f} below threshold {min_confidence}",
            )

        capital = settings.PAPER_INITIAL_CAPITAL
        max_pos_size = capital * (settings.MAX_POSITION_SIZE_PERCENT / 100)
        if size > max_pos_size:
            return RiskCheckResult(
                approved=False,
                reason=f"Position size {size:.2f} exceeds max {max_pos_size:.2f} ({settings.MAX_POSITION_SIZE_PERCENT}% of capital)",
                max_position_size=max_pos_size,
            )

        open_trades = await self._count_open_trades()
        if open_trades >= settings.MAX_OPEN_POSITIONS:
            return RiskCheckResult(
                approved=False,
                reason=f"Open positions {open_trades} >= limit {settings.MAX_OPEN_POSITIONS}",
                max_open_positions=settings.MAX_OPEN_POSITIONS,
            )

        daily_loss = await self._calculate_daily_loss()
        if daily_loss >= settings.MAX_DAILY_LOSS:
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss {daily_loss:.2f} >= limit {settings.MAX_DAILY_LOSS:.2f}",
                max_daily_loss=settings.MAX_DAILY_LOSS,
            )

        cooldown = await self._check_cooldown(market_id)
        if cooldown > 0:
            return RiskCheckResult(
                approved=False,
                reason=f"Cooldown active: {cooldown}s remaining",
                cooldown_remaining=cooldown,
            )

        current_exposure = await self._calculate_exposure()
        if current_exposure >= settings.EXPOSURE_LIMIT:
            return RiskCheckResult(
                approved=False,
                reason=f"Exposure {current_exposure:.2%} >= limit {settings.EXPOSURE_LIMIT:.0%}",
            )

        return RiskCheckResult(approved=True)

    async def _count_open_trades(self) -> int:
        result = await self.db.execute(
            select(func.count(Trade.id)).where(Trade.status.in_(["pending", "open"]))
        )
        return result.scalar() or 0

    async def _calculate_daily_loss(self) -> float:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.db.execute(
            select(func.coalesce(func.sum(Trade.pnl), 0)).where(
                and_(
                    Trade.status == "closed",
                    Trade.exit_timestamp >= today_start,
                    Trade.pnl < 0,
                )
            )
        )
        return abs(float(result.scalar() or 0))

    async def _check_cooldown(self, market_id: UUID | None) -> int:
        if market_id is None:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.COOLDOWN_MINUTES * 60)
        result = await self.db.execute(
            select(Trade.updated_at)
            .where(
                and_(
                    Trade.market_id == market_id,
                    Trade.created_at >= cutoff,
                )
            )
            .order_by(Trade.updated_at.desc())
            .limit(1)
        )
        last_trade_time = result.scalar_one_or_none()
        if last_trade_time:
            elapsed = (datetime.now(timezone.utc) - last_trade_time).total_seconds()
            remaining = max(0, int(settings.COOLDOWN_MINUTES * 60 - elapsed))
            return remaining
        return 0

    async def _calculate_exposure(self) -> float:
        capital = settings.PAPER_INITIAL_CAPITAL
        open_trades = await self.db.execute(
            select(func.coalesce(func.sum(Trade.size), 0)).where(Trade.status.in_(["pending", "open"]))
        )
        total_exposure = float(open_trades.scalar() or 0)
        return total_exposure / capital if capital > 0 else 0
