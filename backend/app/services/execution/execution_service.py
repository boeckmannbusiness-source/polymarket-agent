import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade, ExchangeOrder
from app.exchanges.paper import PaperExchangeAdapter
from app.exchanges.polymarket_live import PolymarketLiveAdapter
from app.core.logging import logger
from app.services.control.control_plane import control_plane
from app.services.risk.circuit_breakers import cb_system


class ExecutionSafetyError(Exception):
    pass


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._live_adapter: PolymarketLiveAdapter | None = None

    async def _check_safety(self, trade: Trade | None = None):
        if not await control_plane.is_trading_enabled():
            raise ExecutionSafetyError("Global trading disabled by control plane")

        if trade and trade.agent_id and await control_plane.is_strategy_paused(trade.agent_id):
            raise ExecutionSafetyError(f"Strategy paused: {trade.agent_id}")

        if trade and trade.market_id and await control_plane.is_market_paused(trade.market_id):
            raise ExecutionSafetyError(f"Market paused: {trade.market_id}")

        active_breakers = await cb_system.get_active()
        if active_breakers:
            names = [b.get("name") for b in active_breakers]
            raise ExecutionSafetyError(f"Active circuit breakers: {names}")

    async def _get_adapter(self, engine_type: str):
        if engine_type == "paper":
            return PaperExchangeAdapter(self.db)
        elif engine_type == "live":
            if self._live_adapter is None:
                self._live_adapter = PolymarketLiveAdapter(self.db)
            return self._live_adapter
        else:
            raise ValueError(f"Unknown engine_type: {engine_type}")

    async def create_trade_execution(self, trade: Trade):
        await self._check_safety(trade)
        engine_type = trade.trade_type or "paper"

        result = await self.db.execute(
            select(ExchangeOrder)
            .where(ExchangeOrder.trade_id == trade.id)
            .order_by(ExchangeOrder.order_num.desc())
            .limit(1)
        )
        last_order = result.scalar_one_or_none()
        order_num = (last_order.order_num + 1) if last_order else 1

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id,
            order_num=order_num,
            engine_type=engine_type,
            exchange="polymarket_clob",
            status="pending",
            side=trade.side,
            outcome=trade.outcome,
            size=Decimal(str(trade.size)),
            price=Decimal(str(trade.price)) if trade.price is not None else None,
            idempotency_key=str(uuid.uuid4()),
        )
        self.db.add(exchange_order)
        await self.db.flush()

        await self.submit_order(exchange_order)
        return exchange_order

    async def submit_order(self, exchange_order: ExchangeOrder):
        await self._check_safety()
        existing = await self.db.execute(
            select(ExchangeOrder).where(
                ExchangeOrder.id == exchange_order.id,
                ExchangeOrder.status.in_(["submitted", "partially_filled", "filled"]),
            )
        )
        if existing.scalar_one_or_none():
            logger.warning(
                "submit_order_idempotent_skip",
                order_id=str(exchange_order.id),
                status=exchange_order.status,
            )
            return

        adapter = await self._get_adapter(exchange_order.engine_type)
        await adapter.submit_order(exchange_order)

        if exchange_order.engine_type == "live":
            logger.info(
                "live_order_submitted_async",
                order_id=str(exchange_order.id),
                status=exchange_order.status,
            )

    async def close_trade_execution(self, trade: Trade, exit_price: Decimal | None = None):
        result = await self.db.execute(
            select(ExchangeOrder)
            .where(
                ExchangeOrder.trade_id == trade.id,
                ExchangeOrder.status.in_(["filled", "partially_filled"]),
            )
            .order_by(ExchangeOrder.order_num)
            .limit(1)
        )
        original_order = result.scalar_one_or_none()
        if not original_order:
            raise ValueError(f"No filled ExchangeOrder found for trade {trade.id}")

        if exit_price is not None:
            resolved_price = Decimal(str(exit_price))
        else:
            from app.engines.paper_engine import PaperEngine
            engine = PaperEngine(self.db)
            if trade.market_id:
                market_price = await engine._get_latest_market_price(trade.market_id)
                if market_price is not None:
                    resolved_price = Decimal(str(engine._outcome_price(market_price, trade.outcome)))
                else:
                    resolved_price = original_order.filled_price or Decimal("0.5")
            else:
                resolved_price = original_order.filled_price or Decimal("0.5")

        close_order_num = original_order.order_num + 1

        close_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id,
            order_num=close_order_num,
            engine_type=original_order.engine_type,
            exchange=original_order.exchange,
            status="pending",
            side="sell" if original_order.side == "buy" else "buy",
            outcome=original_order.outcome,
            size=original_order.filled_size,
            price=resolved_price,
            idempotency_key=str(uuid.uuid4()),
        )
        self.db.add(close_order)
        await self.db.flush()

        await self.submit_order(close_order)
