import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import select
from app.models.trade import Trade
from app.models.fill import Fill
from app.models.exchange_order import ExchangeOrder

@pytest.mark.asyncio
async def test_trades_outcome_nullable_and_market_id_string(db_session):
    solana_market_id = "So11111111111111111111111111111111111111112"
    trade = Trade(
        id=uuid.uuid4(),
        market_id=solana_market_id,
        side="buy",
        outcome=None,
        trade_type="paper",
        status="pending",
        size=Decimal("10.0"),
        price=Decimal("0.5")
    )
    db_session.add(trade)
    await db_session.commit()
    result = await db_session.execute(select(Trade).where(Trade.market_id == solana_market_id))
    retrieved = result.scalar_one()
    assert retrieved.market_id == solana_market_id
    assert retrieved.outcome is None

@pytest.mark.asyncio
async def test_fills_outcome_nullable_and_market_id_string(db_session):
    solana_market_id = "So11111111111111111111111111111111111111112"
    trade = Trade(
        id=uuid.uuid4(),
        market_id=solana_market_id,
        side="buy",
        outcome=None,
        trade_type="paper",
        status="pending",
        size=Decimal("10.0"),
        price=Decimal("0.5")
    )
    db_session.add(trade)
    order = ExchangeOrder(
        id=uuid.uuid4(),
        trade_id=trade.id,
        side="buy",
        outcome=None,
        size=Decimal("10.0"),
        price=Decimal("0.5"),
        idempotency_key=str(uuid.uuid4())
    )
    db_session.add(order)
    await db_session.flush()
    fill = Fill(
        id=uuid.uuid4(),
        exchange_order_id=order.id,
        trade_id=trade.id,
        market_id=solana_market_id,
        fill_num=1,
        side="buy",
        outcome=None,
        size=Decimal("10.0"),
        price=Decimal("0.5"),
        filled_at=datetime.now(timezone.utc)
    )
    db_session.add(fill)
    await db_session.commit()
    result = await db_session.execute(select(Fill).where(Fill.market_id == solana_market_id))
    retrieved = result.scalar_one()
    assert retrieved.market_id == solana_market_id
    assert retrieved.outcome is None

@pytest.mark.asyncio
async def test_exchange_orders_outcome_nullable(db_session):
    solana_market_id = "So11111111111111111111111111111111111111112"
    trade = Trade(
        id=uuid.uuid4(),
        market_id=solana_market_id,
        side="buy",
        outcome=None,
        trade_type="paper",
        status="pending",
        size=Decimal("10.0"),
        price=Decimal("0.5")
    )
    db_session.add(trade)
    await db_session.flush()
    order = ExchangeOrder(
        id=uuid.uuid4(),
        trade_id=trade.id,
        side="buy",
        outcome=None,
        size=Decimal("10.0"),
        price=Decimal("0.5"),
        idempotency_key=str(uuid.uuid4())
    )
    db_session.add(order)
    await db_session.commit()
    result = await db_session.execute(select(ExchangeOrder).where(ExchangeOrder.id == order.id))
    retrieved = result.scalar_one()
    assert retrieved.outcome is None
