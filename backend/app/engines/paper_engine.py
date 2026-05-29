import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, MarketEvent, Position as PositionModel
from app.core.logging import logger


class PaperEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.capital = settings.PAPER_INITIAL_CAPITAL

    async def initialize(self):
        open_positions = await self.db.execute(
            select(PositionModel).where(PositionModel.status == "OPEN")
        )
        open_positions = list(open_positions.scalars().all())
        if open_positions:
            logger.info(
                "paper_engine_initialized",
                open_positions=len(open_positions),
                capital=self.capital,
            )
        else:
            logger.info("paper_engine_initialized_no_open_positions")

    async def _get_latest_market_price(self, market_id: uuid.UUID) -> float | None:
        result = await self.db.execute(
            select(MarketEvent)
            .where(MarketEvent.market_id == market_id)
            .where(MarketEvent.event_type.in_(["price_change", "trade"]))
            .where(MarketEvent.price.isnot(None))
            .order_by(MarketEvent.timestamp.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event and event.price is not None:
            return float(event.price)
        return None

    def _outcome_price(self, market_yes_price: float, outcome: str | None) -> float:
        if outcome == "NO":
            return 1.0 - market_yes_price
        return market_yes_price

    async def execute_market_order(self, trade: Trade) -> dict[str, Any]:
        market_price = None
        if trade.market_id:
            market_price = await self._get_latest_market_price(trade.market_id)

        base_price = market_price if market_price is not None else (trade.price or 0.5)
        base_price = self._outcome_price(base_price, trade.outcome)

        slippage = 0.001
        fill_price = base_price * (1 + slippage) if trade.side == "buy" else base_price * (1 - slippage)
        fee = trade.size * 0.001
        filled_size = trade.size

        trade.status = "open"
        trade.filled_size = filled_size
        trade.filled_price = fill_price
        trade.slippage = slippage
        trade.fee = fee
        trade.entry_timestamp = datetime.now(timezone.utc)

        logger.info(
            "paper_order_filled",
            trade_id=str(trade.id),
            side=trade.side,
            outcome=trade.outcome,
            size=filled_size,
            price=fill_price,
            slippage=slippage,
            fee=fee,
            market_price=market_price,
        )

        await self.db.flush()

        return {
            "status": "open",
            "filled_size": filled_size,
            "filled_price": fill_price,
            "slippage": slippage,
            "fee": fee,
        }

    async def evaluate_stop_loss_take_profit(self, trade: Trade) -> str | None:
        if trade.status != "open" or trade.market_id is None:
            return None
        if trade.stop_loss is None and trade.take_profit is None:
            return None

        market_price = await self._get_latest_market_price(trade.market_id)
        if market_price is None:
            return None

        current_outcome_price = self._outcome_price(market_price, trade.outcome)
        filled_price = trade.filled_price or 0.5

        if trade.stop_loss is not None:
            if trade.side == "buy" and current_outcome_price <= float(trade.stop_loss):
                return "stop_loss"
            if trade.side == "sell" and current_outcome_price >= float(trade.stop_loss):
                return "stop_loss"

        if trade.take_profit is not None:
            if trade.side == "buy" and current_outcome_price >= float(trade.take_profit):
                return "take_profit"
            if trade.side == "sell" and current_outcome_price <= float(trade.take_profit):
                return "take_profit"

        return None

    async def close_position(self, trade: Trade, exit_price: float | None = None) -> dict[str, Any]:
        if exit_price is None:
            if trade.market_id:
                market_price = await self._get_latest_market_price(trade.market_id)
                if market_price is not None:
                    exit_price = self._outcome_price(market_price, trade.outcome)

        if exit_price is None:
            exit_price = trade.filled_price or 0.5

        if trade.side == "buy":
            pnl = (exit_price - (trade.filled_price or 0.5)) * trade.filled_size
        else:
            pnl = ((trade.filled_price or 0.5) - exit_price) * trade.filled_size

        pnl_percent = pnl / ((trade.filled_price or 0.5) * trade.filled_size) * 100 if trade.filled_size > 0 else 0

        trade.status = "closed"
        trade.pnl = pnl
        trade.pnl_percent = pnl_percent
        trade.exit_timestamp = datetime.now(timezone.utc)

        logger.info(
            "paper_position_closed",
            trade_id=str(trade.id),
            side=trade.side,
            outcome=trade.outcome,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_price=exit_price,
        )

        await self.db.flush()

        return {
            "status": "closed",
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_price": exit_price,
        }
