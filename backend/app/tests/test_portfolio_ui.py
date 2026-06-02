import pytest
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models import Trade, ExchangeOrder, Fill, Position, Market
from app.schemas.portfolio import PortfolioSnapshot, PositionView, TradeTimeline, TradeTimelineEvent
from app.services.portfolio.portfolio_snapshot_service import PortfolioSnapshotService
from app.services.portfolio.strategy_performance_service import StrategyPerformanceService
from app.services.portfolio.execution_timeline_service import ExecutionTimelineService
from app.services.portfolio.position_view_service import PositionViewService
from app.services.portfolio.exposure_service import ExposureService
from app.services.portfolio.portfolio_cache_service import PortfolioCacheService


class TestPortfolioSnapshotAccuracy:
    @pytest.mark.asyncio
    async def test_snapshot_matches_fill_derived_positions(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        pos = Position(
            market_id=market_id,
            direction="BUY", size=Decimal("50"),
            entry_price=Decimal("0.55"), current_price=Decimal("0.60"),
            unrealized_pnl=Decimal("2.5"), status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(pos)
        await db_session.flush()

        service = PortfolioSnapshotService(db_session)
        snapshot = await service.get_portfolio_snapshot()

        assert snapshot.total_equity > 0
        assert snapshot.unrealized_pnl == 2.5
        assert len(snapshot.positions) == 1
        assert snapshot.positions[0].size == 50.0
        assert snapshot.positions[0].unrealized_pnl == 2.5


class TestStrategyPnlCurveCorrectness:
    @pytest.mark.asyncio
    async def test_pnl_curve_monotonic_accumulation(self, db_session):
        agent_id = "test_agent"
        market_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("100"),
            status="closed", agent_id=agent_id,
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("100"), filled_price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.50"),
            fee=Decimal("0.05"),
            filled_at=now,
        )
        db_session.add(fill)

        fill2 = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=market_id, fill_num=2,
            side="sell", outcome="YES",
            size=Decimal("25"), price=Decimal("0.60"),
            fee=Decimal("0.03"),
            filled_at=now + timedelta(hours=1),
        )
        db_session.add(fill2)
        await db_session.flush()

        service = StrategyPerformanceService(db_session)
        curve = await service.get_strategy_pnl_curve(agent_id)

        assert len(curve) > 0
        assert curve[0].cumulative_pnl < 0
        if len(curve) > 1:
            assert curve[-1].cumulative_pnl > curve[0].cumulative_pnl


class TestTradeTimelineOrdering:
    @pytest.mark.asyncio
    async def test_timeline_correct_event_sequence(self, db_session):
        trade_id = uuid.uuid4()
        market_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        trade = Trade(
            id=trade_id, market_id=market_id,
            side="buy", outcome="YES", size=Decimal("100"),
            status="open", created_at=now,
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("100"), filled_price=Decimal("0.55"),
            submitted_at=now + timedelta(seconds=1),
            filled_at=now + timedelta(seconds=5),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            fee=Decimal("0.10"),
            filled_at=now + timedelta(seconds=3),
        )
        db_session.add(fill)
        await db_session.flush()

        service = ExecutionTimelineService(db_session)
        timeline = await service.get_trade_timeline(trade_id)

        assert len(timeline.events) >= 3

        event_types = [e.event_type for e in timeline.events]
        assert event_types[0] == "TradeCreated"
        assert "OrderSubmitted" in event_types
        assert "FillEvent" in event_types
        assert "OrderFilled" in event_types

        timestamps = [e.timestamp for e in timeline.events if e.timestamp]
        assert all(timestamps[i] <= timestamps[i + 1] for i in range(len(timestamps) - 1))


class TestPositionViewConsistency:
    @pytest.mark.asyncio
    async def test_position_view_matches_monitoring(self, db_session):
        market_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        pos = Position(
            market_id=market_id,
            direction="BUY", size=Decimal("75"),
            entry_price=Decimal("0.50"), current_price=Decimal("0.65"),
            unrealized_pnl=Decimal("11.25"), status="OPEN",
            opened_at=now,
        )
        db_session.add(pos)
        await db_session.flush()

        service = PositionViewService(db_session)
        views = await service.get_positions_overview()

        assert len(views) == 1
        view = views[0]
        assert view.size == 75.0
        assert view.entry_price == 0.50
        assert view.current_price == 0.65
        assert view.unrealized_pnl == 11.25


class TestCacheInvalidationOnFillEvent:
    @pytest.mark.asyncio
    async def test_cache_invalidation_clears_keys(self):
        cache = PortfolioCacheService(redis_enabled=False)

        await cache.set("snapshot:overview", {"test": "data"}, ttl_seconds=60)
        await cache.set("position_view:all", [{"test": "data"}], ttl_seconds=60)

        cached = await cache.get("snapshot:overview")
        assert cached == {"test": "data"}

        await cache.invalidate_on_fill()

        cached = await cache.get("snapshot:overview")
        assert cached is None

        cached = await cache.get("position_view:all")
        assert cached is None

    @pytest.mark.asyncio
    async def test_cache_does_not_invalidate_unrelated_keys(self):
        cache = PortfolioCacheService(redis_enabled=False)

        await cache.set("snapshot:overview", {"v": 1}, ttl_seconds=60)
        await cache.set("trade_timeline:abc", {"v": 3}, ttl_seconds=60)

        await cache.invalidate_on_fill()

        assert await cache.get("snapshot:overview") is None
        assert await cache.get("trade_timeline:abc") is not None


class TestExposureService:
    @pytest.mark.asyncio
    async def test_market_exposure_aggregation(self, db_session):
        market_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        pos1 = Position(
            market_id=market_id,
            direction="BUY", size=Decimal("100"),
            entry_price=Decimal("0.50"), current_price=Decimal("0.55"),
            unrealized_pnl=Decimal("5.0"), status="OPEN",
            opened_at=now,
        )
        pos2 = Position(
            market_id=uuid.uuid4(),
            direction="SELL", size=Decimal("50"),
            entry_price=Decimal("0.60"), current_price=Decimal("0.55"),
            unrealized_pnl=Decimal("2.5"), status="OPEN",
            opened_at=now,
        )
        db_session.add_all([pos1, pos2])
        await db_session.flush()

        service = ExposureService(db_session)
        exposure = await service.get_market_exposure()

        assert exposure.total_long_exposure > 0
        assert exposure.total_short_exposure > 0
        assert len(exposure.exposure_by_market) == 2


class TestStrategyKPIComputation:
    @pytest.mark.asyncio
    async def test_strategy_summary_returns_kpis(self, db_session):
        agent_id = "perf_agent"
        market_id = uuid.uuid4()

        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"),
            status="closed", agent_id=agent_id,
            pnl=Decimal("10.0"),
            entry_timestamp=datetime.now(timezone.utc) - timedelta(hours=24),
            exit_timestamp=datetime.now(timezone.utc),
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            filled_size=Decimal("50"), filled_price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            fee=Decimal("0.05"),
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        service = StrategyPerformanceService(db_session)
        summary = await service.get_strategy_summary(agent_id)

        assert summary.agent_id == agent_id
        assert summary.total_trades == 1
        assert summary.win_rate >= 0
        assert summary.cumulative_pnl is not None
        assert len(summary.pnl_curve) > 0
