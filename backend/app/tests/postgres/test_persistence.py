import pytest
import uuid
import os
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from app.database import Base
from app.models.trade import Trade
from app.models.fill import Fill
from app.models.exchange_order import ExchangeOrder
from app.models.execution_trace import ExecutionTrace
from app.models.signal import Signal
from app.models.market import Market

# Use environment variable if available, else fallback to a default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")

@pytest.fixture(scope="module")
async def engine():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def session(engine):
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_persist_trade_order_and_fill(session: AsyncSession):
    trade_id = uuid.uuid4()
    trade = Trade(
        id=trade_id,
        market_id="SOL-USDC",
        side="buy",
        size=Decimal("1.0"),
        price=Decimal("100.0"),
        status="open",
        agent_id="test_agent",
        created_at=datetime.now(timezone.utc)
    )
    session.add(trade)

    order_id = uuid.uuid4()
    order = ExchangeOrder(
        id=order_id,
        trade_id=trade_id,
        order_num=1,
        side="buy",
        size=Decimal("1.0"),
        price=Decimal("100.0"),
        status="filled",
        idempotency_key=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc)
    )
    session.add(order)

    fill_id = uuid.uuid4()
    fill = Fill(
        id=fill_id,
        trade_id=trade_id,
        exchange_order_id=order_id,
        market_id="SOL-USDC",
        side="buy",
        size=Decimal("1.0"),
        price=Decimal("100.0"),
        fee=Decimal("0.001"),
        fill_num=1,
        filled_at=datetime.now(timezone.utc)
    )
    session.add(fill)
    await session.commit()

    # Verify Trade
    result = await session.execute(select(Trade).where(Trade.id == trade_id))
    persisted_trade = result.scalar_one()
    assert persisted_trade.market_id == "SOL-USDC"

    # Verify Fill
    result = await session.execute(select(Fill).where(Fill.id == fill_id))
    persisted_fill = result.scalar_one()
    assert persisted_fill.trade_id == trade_id
    assert persisted_fill.price == Decimal("100.0")

@pytest.mark.asyncio
async def test_persist_execution_trace(session: AsyncSession):
    trace_id = uuid.uuid4()
    trace = ExecutionTrace(
        id=trace_id,
        execution_side="buy",
        execution_size=1.0,
        fill_status="filled",
        fill_price=100.0,
        fill_size=1.0,
        created_at=datetime.now(timezone.utc)
    )
    session.add(trace)
    await session.commit()

    result = await session.execute(select(ExecutionTrace).where(ExecutionTrace.id == trace_id))
    persisted_trace = result.scalar_one()
    assert persisted_trace.execution_side == "buy"
    assert persisted_trace.fill_price == 100.0
