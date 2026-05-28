from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade
from app.services.pipeline_metrics import inc_exposure_rejection


MAX_TOTAL_EXPOSURE_USD = 20
MAX_POSITION_SIZE_USD = 2
MAX_OPEN_POSITIONS = 3
MAX_MARKET_EXPOSURE_USD = 5


@dataclass
class ExposureCheckResult:
    approved: bool
    reason: str
    current_open_exposure: float
    pending_exposure: float
    exposure_by_market: dict[str, float]
    position_count: int


class GlobalRiskGuard:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_exposure(
        self,
        market_id: str,
        outcome: str,
        proposed_size: float,
        proposed_price: float,
    ) -> ExposureCheckResult:
        result = await self.db.execute(
            select(Trade).where(
                Trade.status.in_(["open", "pending"]),
            )
        )
        open_trades = list(result.scalars().all())

        current_open_exposure = 0.0
        exposure_by_market: dict[str, float] = {}
        position_count = len(open_trades)

        for t in open_trades:
            filled = float(t.filled_size or 0)
            price = float(t.filled_price or 0)
            exposure = filled * price if price > 0 else 0
            current_open_exposure += exposure
            mid = str(t.market_id)
            exposure_by_market[mid] = exposure_by_market.get(mid, 0) + exposure

        pending_exposure = proposed_size * proposed_price
        total_exposure = current_open_exposure + pending_exposure

        if total_exposure > MAX_TOTAL_EXPOSURE_USD:
            await inc_exposure_rejection()
            return ExposureCheckResult(
                approved=False,
                reason=f"total_exposure_{total_exposure:.2f}_exceeds_max_{MAX_TOTAL_EXPOSURE_USD}",
                current_open_exposure=current_open_exposure,
                pending_exposure=pending_exposure,
                exposure_by_market=exposure_by_market,
                position_count=position_count,
            )

        if proposed_size * proposed_price > MAX_POSITION_SIZE_USD:
            await inc_exposure_rejection()
            return ExposureCheckResult(
                approved=False,
                reason=f"position_size_{proposed_size*proposed_price:.2f}_exceeds_max_{MAX_POSITION_SIZE_USD}",
                current_open_exposure=current_open_exposure,
                pending_exposure=pending_exposure,
                exposure_by_market=exposure_by_market,
                position_count=position_count,
            )

        if position_count >= MAX_OPEN_POSITIONS:
            await inc_exposure_rejection()
            return ExposureCheckResult(
                approved=False,
                reason=f"position_count_{position_count}_exceeds_max_{MAX_OPEN_POSITIONS}",
                current_open_exposure=current_open_exposure,
                pending_exposure=pending_exposure,
                exposure_by_market=exposure_by_market,
                position_count=position_count,
            )

        market_exposure = exposure_by_market.get(market_id, 0) + pending_exposure
        if market_exposure > MAX_MARKET_EXPOSURE_USD:
            await inc_exposure_rejection()
            return ExposureCheckResult(
                approved=False,
                reason=f"market_exposure_{market_exposure:.2f}_exceeds_max_{MAX_MARKET_EXPOSURE_USD}",
                current_open_exposure=current_open_exposure,
                pending_exposure=pending_exposure,
                exposure_by_market=exposure_by_market,
                position_count=position_count,
            )

        return ExposureCheckResult(
            approved=True,
            reason="all_exposure_limits_ok",
            current_open_exposure=current_open_exposure,
            pending_exposure=pending_exposure,
            exposure_by_market=exposure_by_market,
            position_count=position_count,
        )

    async def get_exposure_summary(self) -> dict[str, Any]:
        result = await self.db.execute(
            select(Trade).where(
                Trade.status.in_(["open", "pending"]),
            )
        )
        open_trades = list(result.scalars().all())

        total_exposure = 0.0
        exposure_by_market: dict[str, float] = {}

        for t in open_trades:
            filled = float(t.filled_size or 0)
            price = float(t.filled_price or 0)
            exposure = filled * price if price > 0 else 0
            total_exposure += exposure
            mid = str(t.market_id)
            exposure_by_market[mid] = exposure_by_market.get(mid, 0) + exposure

        return {
            "total_open_exposure": round(total_exposure, 2),
            "max_total_exposure": MAX_TOTAL_EXPOSURE_USD,
            "exposure_utilization_pct": round(total_exposure / MAX_TOTAL_EXPOSURE_USD * 100, 1) if MAX_TOTAL_EXPOSURE_USD > 0 else 0,
            "position_count": len(open_trades),
            "max_open_positions": MAX_OPEN_POSITIONS,
            "max_position_size_usd": MAX_POSITION_SIZE_USD,
            "max_market_exposure_usd": MAX_MARKET_EXPOSURE_USD,
            "exposure_by_market": {k: round(v, 2) for k, v in exposure_by_market.items()},
        }
