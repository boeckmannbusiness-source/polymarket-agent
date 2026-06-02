import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import Trade, ExchangeOrder, Fill


class TestTradeExchangeOrderRelationship:
    """Trade ↔ ExchangeOrder bidirectional relationship (1:N)"""

    @pytest.mark.asyncio
    async def test_trade_has_orders(self, db_session):
        trade = Trade(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id,
            order_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        result = await db_session.execute(
            select(Trade).where(Trade.id == trade.id).options(selectinload(Trade.orders))
        )
        loaded_trade = result.scalar_one()
        assert len(loaded_trade.orders) == 1
        assert loaded_trade.orders[0].id == order.id

    @pytest.mark.asyncio
    async def test_order_belongs_to_trade(self, db_session):
        trade = Trade(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            side="buy",
            outcome="YES",
            size=Decimal("100"),
            status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id,
            order_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("100"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        assert order.trade.id == trade.id
        assert order.trade.side == "buy"

    @pytest.mark.asyncio
    async def test_trade_can_have_multiple_orders(self, db_session):
        trade = Trade(
            id=uuid.uuid4(),
            market_id=uuid.uuid4(),
            side="buy",
            outcome="YES",
            size=Decimal("100"),
            status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order1 = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        order2 = ExchangeOrder(
            trade_id=trade.id, order_num=2,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add_all([order1, order2])
        await db_session.flush()

        result = await db_session.execute(
            select(Trade).where(Trade.id == trade.id).options(selectinload(Trade.orders))
        )
        loaded_trade = result.scalar_one()
        assert len(loaded_trade.orders) == 2
        assert {o.id for o in loaded_trade.orders} == {order1.id, order2.id}


class TestExchangeOrderFillRelationship:
    """ExchangeOrder ↔ Fill relationship (1:N)"""

    @pytest.mark.asyncio
    async def test_exchange_order_has_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("100"),
            idempotency_key=str(uuid.uuid4()), status="submitted",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id,
            trade_id=trade.id,
            market_id=trade.market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("60"),
            price=Decimal("0.55"),
            fee=Decimal("0.06"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        result = await db_session.execute(
            select(ExchangeOrder).where(ExchangeOrder.id == order.id).options(selectinload(ExchangeOrder.fills))
        )
        loaded_order = result.scalar_one()
        assert len(loaded_order.fills) == 1
        assert loaded_order.fills[0].id == fill.id

    @pytest.mark.asyncio
    async def test_fill_belongs_to_exchange_order(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="submitted",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id,
            trade_id=trade.id,
            market_id=trade.market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        assert fill.exchange_order.id == order.id
        assert fill.exchange_order.status == "submitted"

    @pytest.mark.asyncio
    async def test_exchange_order_can_have_multiple_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("100"),
            idempotency_key=str(uuid.uuid4()), status="partially_filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill1 = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="buy", outcome="YES",
            size=Decimal("30"), price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        fill2 = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=2, side="buy", outcome="YES",
            size=Decimal("70"), price=Decimal("0.56"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add_all([fill1, fill2])
        await db_session.flush()

        result = await db_session.execute(
            select(ExchangeOrder).where(ExchangeOrder.id == order.id).options(selectinload(ExchangeOrder.fills))
        )
        loaded_order = result.scalar_one()
        assert len(loaded_order.fills) == 2
        assert {f.fill_num for f in loaded_order.fills} == {1, 2}


class TestTradeFillDirectRelationship:
    """Trade ↔ Fill direct relationship (no cascade on Trade.fills)"""

    @pytest.mark.asyncio
    async def test_trade_has_fills_readonly(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id,
            trade_id=trade.id,
            market_id=trade.market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        result = await db_session.execute(
            select(Trade).where(Trade.id == trade.id).options(selectinload(Trade.fills))
        )
        loaded_trade = result.scalar_one()
        assert len(loaded_trade.fills) == 1
        assert loaded_trade.fills[0].id == fill.id

    @pytest.mark.asyncio
    async def test_fill_belongs_to_trade(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id,
            trade_id=trade.id,
            market_id=trade.market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("50"),
            price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        assert fill.trade.id == trade.id
        assert fill.trade.outcome == "YES"


class TestCascadeBehavior:
    """Cascade: Trade → ExchangeOrder → Fill"""

    @pytest.mark.asyncio
    async def test_delete_trade_cascades_to_exchange_orders(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        await db_session.delete(trade)
        await db_session.flush()

        remaining = await db_session.execute(
            select(ExchangeOrder).where(ExchangeOrder.id == order.id)
        )
        assert remaining.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_exchange_order_cascades_to_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="submitted",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="buy", outcome="YES",
            size=Decimal("25"), price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        await db_session.delete(order)
        await db_session.flush()

        remaining = await db_session.execute(
            select(Fill).where(Fill.id == fill.id)
        )
        assert remaining.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_trade_cascades_through_to_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        await db_session.delete(trade)
        await db_session.flush()

        order_remaining = await db_session.execute(
            select(ExchangeOrder).where(ExchangeOrder.id == order.id)
        )
        assert order_remaining.scalar_one_or_none() is None

        fill_remaining = await db_session.execute(
            select(Fill).where(Fill.id == fill.id)
        )
        assert fill_remaining.scalar_one_or_none() is None


class TestUniqueConstraints:
    """Unique constraint enforcement"""

    @pytest.mark.asyncio
    async def test_idempotency_key_unique(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        key = str(uuid.uuid4())
        order1 = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=key,
        )
        db_session.add(order1)
        await db_session.flush()

        order2 = ExchangeOrder(
            trade_id=trade.id, order_num=2,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=key,
        )
        db_session.add(order2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_clob_order_id_unique(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order1 = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
            clob_order_id="clob-001",
        )
        db_session.add(order1)
        await db_session.flush()

        order2 = ExchangeOrder(
            trade_id=trade.id, order_num=2,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
            clob_order_id="clob-001",
        )
        db_session.add(order2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_unique_clob_fill_id(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill1 = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_fill_id="clob-fill-001",
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill1)
        await db_session.flush()

        fill2 = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=2, side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_fill_id="clob-fill-001",
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestCheckConstraints:
    """CheckConstraint violation enforcement"""

    @pytest.mark.asyncio
    async def test_reject_invalid_exchange_order_status(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
            status="invalid",
        )
        db_session.add(order)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_reject_invalid_exchange_order_side(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="INVALID", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_reject_invalid_exchange_order_outcome(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="MAYBE", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_reject_invalid_fill_side(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="INVALID", outcome="YES",
            size=Decimal("25"), price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_reject_invalid_fill_outcome(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id, market_id=trade.market_id,
            fill_num=1, side="buy", outcome="MAYBE",
            size=Decimal("25"), price=Decimal("0.55"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestFillFieldConstraints:
    """Field-level constraint enforcement (NOT NULL, types)"""

    @pytest.mark.asyncio
    async def test_fill_requires_market_id(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        with pytest.raises((IntegrityError, Exception)):
            fill = Fill(
                exchange_order_id=order.id,
                trade_id=trade.id,
                market_id=None,
                fill_num=1,
                side="buy",
                outcome="YES",
                size=Decimal("25"),
                price=Decimal("0.55"),
                filled_at=datetime.now(timezone.utc),
            )
            db_session.add(fill)
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_fill_uses_decimal_not_float(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            trade_id=trade.id, order_num=1,
            side="buy", outcome="YES", size=Decimal("50"),
            idempotency_key=str(uuid.uuid4()), status="filled",
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id,
            trade_id=trade.id,
            market_id=trade.market_id,
            fill_num=1,
            side="buy",
            outcome="YES",
            size=Decimal("25"),
            price=Decimal("0.55"),
            fee=Decimal("0.03"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        assert isinstance(fill.size, Decimal)
        assert isinstance(fill.price, Decimal)
        assert isinstance(fill.fee, Decimal)
