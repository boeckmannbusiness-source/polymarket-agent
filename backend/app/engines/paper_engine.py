import random
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Trade, Market, MarketEvent
from app.core.logging import logger


class PaperEngine:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.capital = settings.PAPER_INITIAL_CAPITAL
        self.positions: dict[uuid.UUID, dict] = {}

    async def execute_market_order(self, trade: Trade) -> dict[str, Any]:
        slippage = random.uniform(0.001, 0.005)
        fill_price = (trade.price or 0.5) * (1 + slippage) if trade.side == "buy" else (trade.price or 0.5) * (1 - slippage)
        fee = trade.size * 0.001
        filled_size = trade.size

        trade.status = "open"
        trade.filled_size = filled_size
        trade.filled_price = fill_price
        trade.slippage = slippage
        trade.fee = fee
        trade.entry_timestamp = datetime.now(timezone.utc)

        if not trade.stop_loss:
            trade.stop_loss = fill_price * (1 - settings.STOP_LOSS_PERCENT / 100)
        if not trade.take_profit:
            trade.take_profit = fill_price * (1 + settings.TAKE_PROFIT_PERCENT / 100)

        self.positions[trade.id] = {
            "entry_price": fill_price,
            "size": filled_size,
            "side": trade.side,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
        }

        logger.info(
            "paper_order_filled",
            trade_id=str(trade.id),
            side=trade.side,
            size=filled_size,
            price=fill_price,
            slippage=slippage,
            fee=fee,
        )

        await self.db.flush()

        return {
            "status": "open",
            "filled_size": filled_size,
            "filled_price": fill_price,
            "slippage": slippage,
            "fee": fee,
        }

    async def close_position(self, trade: Trade) -> dict[str, Any]:
        position = self.positions.get(trade.id)
        if not position:
            current_price = trade.filled_price or 0.5
            exit_price = current_price * (0.98 if trade.side == "buy" else 1.02)
        else:
            entry = position["entry_price"]
            direction = 1 if position["side"] == "buy" else -1
            exit_price = entry * (0.98 if trade.side == "buy" else 1.02)

        if trade.side == "buy":
            pnl = (exit_price - (trade.filled_price or 0.5)) * trade.filled_size
        else:
            pnl = ((trade.filled_price or 0.5) - exit_price) * trade.filled_size

        pnl_percent = pnl / ((trade.filled_price or 0.5) * trade.filled_size) * 100 if trade.filled_size > 0 else 0

        trade.status = "closed"
        trade.pnl = pnl
        trade.pnl_percent = pnl_percent
        trade.exit_timestamp = datetime.now(timezone.utc)

        self.positions.pop(trade.id, None)

        logger.info(
            "paper_position_closed",
            trade_id=str(trade.id),
            pnl=pnl,
            pnl_percent=pnl_percent,
        )

        await self.db.flush()

        return {
            "status": "closed",
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "exit_price": exit_price,
        }

    async def check_stop_loss_take_profit(self) -> list[uuid.UUID]:
        closed = []
        for trade_id, position in list(self.positions.items()):
            current_price = position["entry_price"] * random.uniform(0.95, 1.05)
            if position["side"] == "buy":
                if current_price <= position["stop_loss"]:
                    trade = await self.db.execute(
                        select(Trade).where(Trade.id == trade_id)
                    )
                    trade = trade.scalar_one_or_none()
                    if trade:
                        await self.close_position(trade)
                        closed.append(trade_id)
                elif current_price >= position["take_profit"]:
                    trade = await self.db.execute(
                        select(Trade).where(Trade.id == trade_id)
                    )
                    trade = trade.scalar_one_or_none()
                    if trade:
                        await self.close_position(trade)
                        closed.append(trade_id)
        return closed
