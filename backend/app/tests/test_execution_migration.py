import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models import Trade, ExchangeOrder, Fill, Position
from app.exchanges.paper import PaperExchangeAdapter
from app.services.execution.execution_service import ExecutionService
from app.services.execution.fill_handler import FillHandler


class TestTradeIsNotMutatedByExecution:
    """Trade execution fields must remain unchanged after PaperExchangeAdapter processes an order."""

    @pytest.mark.asyncio
    async def test_trade_execution_fields_unchanged_after_submit(self, db_session):
        trade = Trade(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            side="buy",
            outcome="YES",
            size=Decimal("100"),
            price=Decimal("0.55"),
            status="pending",
            filled_size=0,
            filled_price=None,
            slippage=None,
            fee=None,
            pnl=None,
            pnl_percent=None,
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id,
            order_num=1,
            engine_type="paper",
            exchange="polymarket_clob",
            status="pending",
            side="buy",
            outcome="YES",
            size=Decimal("100"),
            price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        adapter = PaperExchangeAdapter(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await adapter.submit_order(exchange_order)

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.filled_price is None
        assert trade.slippage is None
        assert trade.fee is None
        assert trade.pnl is None

    @pytest.mark.asyncio
    async def test_trade_create_via_execution_service_no_field_writes(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("100"),
            price=Decimal("0.55"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        service = ExecutionService(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await service.create_trade_execution(trade)

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.filled_price is None
        assert trade.slippage is None
        assert trade.fee is None


class TestExchangeOrderCreatesFills:
    """Submitting an order via PaperExchangeAdapter must create Fill rows."""

    @pytest.mark.asyncio
    async def test_submit_order_creates_fill(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()), status="pending",
            engine_type="paper",
            exchange="polymarket_clob",
        )
        db_session.add(exchange_order)
        await db_session.flush()

        adapter = PaperExchangeAdapter(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await adapter.submit_order(exchange_order)

        fills = await db_session.execute(
            select(Fill).where(Fill.exchange_order_id == exchange_order.id)
        )
        fill_list = list(fills.scalars().all())
        assert len(fill_list) == 1
        fill = fill_list[0]
        assert fill.trade_id == trade.id
        assert fill.market_id == trade.market_id
        assert fill.side == "buy"
        assert fill.outcome == "YES"
        assert fill.size == Decimal("50")
        assert fill.price > 0
        assert fill.fee >= 0

    @pytest.mark.asyncio
    async def test_fill_has_correct_slippage_price(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("100"),
            price=Decimal("0.50"),
            idempotency_key=str(uuid.uuid4()), status="pending",
            engine_type="paper", exchange="polymarket_clob",
        )
        db_session.add(exchange_order)
        await db_session.flush()

        adapter = PaperExchangeAdapter(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await adapter.submit_order(exchange_order)

        assert exchange_order.status == "filled"
        assert exchange_order.filled_size == Decimal("100")
        assert exchange_order.filled_price == Decimal("0.5005")
        assert exchange_order.slippage == Decimal("0.001")


class TestFillUpdatesPositionOnly:
    """Fill to Position update is the ONLY source of truth for position changes."""

    @pytest.mark.asyncio
    async def test_fill_creates_position(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()), status="filled",
            engine_type="paper", exchange="polymarket_clob",
            filled_size=Decimal("50"),
            filled_price=Decimal("0.551"),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=exchange_order.id,
            trade_id=trade.id,
            market_id=market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            price=Decimal("0.55"),
            fee=Decimal("0.05"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        handler = FillHandler(db_session)
        await handler.process_fill(fill)

        positions = await db_session.execute(
            select(Position).where(Position.market_id == market_id)
        )
        pos_list = list(positions.scalars().all())
        assert len(pos_list) == 1
        pos = pos_list[0]
        assert pos.direction == "BUY"
        assert pos.size == 50.0

    @pytest.mark.asyncio
    async def test_fill_closes_position(self, db_session):
        market_id = uuid.uuid4()

        pos = Position(
            market_id=market_id,
            direction="BUY",
            size=50.0,
            entry_price=0.55,
            current_price=0.55,
            status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        await db_session.flush()

        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="sell", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=2,
            side="sell", outcome="YES", size=Decimal("50"),
            price=Decimal("0.60"),
            idempotency_key=str(uuid.uuid4()), status="filled",
            engine_type="paper", exchange="polymarket_clob",
            filled_size=Decimal("50"),
            filled_price=Decimal("0.60"),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=exchange_order.id,
            trade_id=trade.id,
            market_id=market_id,
            fill_num=1,
            side="sell",
            outcome="YES",
            size=Decimal("50"),
            price=Decimal("0.60"),
            fee=Decimal("0"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        handler = FillHandler(db_session)
        await handler.process_fill(fill)

        await db_session.refresh(pos)
        assert pos.status == "CLOSED"
        assert pos.size == 0
        assert pos.realized_pnl == pytest.approx(2.5, rel=1e-3)


class TestNoTradeFieldWrites:
    """Verify no writes to Trade execution fields occur through the new pipeline."""

    @pytest.mark.asyncio
    async def test_execution_service_does_not_write_trade_fields(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        service = ExecutionService(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await service.create_trade_execution(trade)

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.filled_price is None
        assert trade.slippage is None
        assert trade.fee is None

    @pytest.mark.asyncio
    async def test_multiple_fills_no_trade_mutation(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order1 = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            price=Decimal("0.50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
            engine_type="paper", exchange="polymarket_clob",
            filled_size=Decimal("50"), filled_price=Decimal("0.501"),
        )
        db_session.add(order1)
        await db_session.flush()

        fill1 = Fill(
            exchange_order_id=order1.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.501"),
            fee=Decimal("0.05"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill1)
        await db_session.flush()

        handler = FillHandler(db_session)
        await handler.process_fill(fill1)

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.pnl is None

        order2 = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=2,
            side="sell", outcome="YES", size=Decimal("50"),
            price=Decimal("0.60"),
            idempotency_key=str(uuid.uuid4()), status="filled",
            engine_type="paper", exchange="polymarket_clob",
            filled_size=Decimal("50"), filled_price=Decimal("0.60"),
        )
        db_session.add(order2)
        await db_session.flush()

        fill2 = Fill(
            exchange_order_id=order2.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="sell", outcome="YES",
            size=Decimal("50"), price=Decimal("0.60"),
            fee=Decimal("0"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill2)
        await db_session.flush()

        await handler.process_fill(fill2)

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.pnl is None
        assert trade.filled_price is None


class TestExchangeOrderIsMutableExecutionState:
    """ExchangeOrder is the ONLY mutable execution state."""

    @pytest.mark.asyncio
    async def test_exchange_order_updated_after_submit(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(),
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()), status="pending",
            engine_type="paper", exchange="polymarket_clob",
        )
        db_session.add(exchange_order)
        await db_session.flush()

        adapter = PaperExchangeAdapter(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock(return_value=None)):
            await adapter.submit_order(exchange_order)

        assert exchange_order.status == "filled"
        assert exchange_order.filled_size == Decimal("50")
        assert exchange_order.filled_price is not None
        assert exchange_order.filled_at is not None
