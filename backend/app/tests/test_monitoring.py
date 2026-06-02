import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models import Trade, ExchangeOrder, Fill, Position
from app.services.monitoring.execution_metrics_service import ExecutionMetricsService
from app.services.monitoring.pnl_service import PnLService
from app.services.monitoring.order_state_service import OrderStateService
from app.services.monitoring.drift_service import DriftDetectionService
from app.services.monitoring.event_stream_service import EventStreamService


class TestTradeMetricsAccuracy:
    """Fill-based aggregation must be correct."""

    @pytest.mark.asyncio
    async def test_trade_metrics_from_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
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

        fill1 = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("60"), price=Decimal("0.55"),
            fee=Decimal("0.06"), filled_at=datetime.now(timezone.utc),
        )
        fill2 = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=2,
            side="buy", outcome="YES",
            size=Decimal("40"), price=Decimal("0.56"),
            fee=Decimal("0.04"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add_all([fill1, fill2])
        await db_session.flush()

        svc = ExecutionMetricsService(db_session)
        metrics = await svc.get_trade_metrics(trade.id)

        assert metrics["fill_count"] == 2
        assert metrics["total_filled"] == 100.0
        assert metrics["total_fees"] == 0.10
        assert metrics["total_requested"] == 100.0

    @pytest.mark.asyncio
    async def test_trade_metrics_empty_trade(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        svc = ExecutionMetricsService(db_session)
        metrics = await svc.get_trade_metrics(trade.id)

        assert metrics["fill_count"] == 0
        assert metrics["total_filled"] == 0.0


class TestPnlCalculationFromFillsOnly:
    """PnL must be derived ONLY from Fill data, never from Trade fields."""

    @pytest.mark.asyncio
    async def test_realized_pnl_from_fills(self, db_session):
        market_id = uuid.uuid4()
        trade_buy = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade_buy)
        await db_session.flush()

        order_buy = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade_buy.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            filled_size=Decimal("50"), filled_price=Decimal("0.55"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order_buy)
        await db_session.flush()

        fill_buy = Fill(
            exchange_order_id=order_buy.id, trade_id=trade_buy.id,
            market_id=market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            fee=Decimal("0.05"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill_buy)
        await db_session.flush()

        trade_sell = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="sell", outcome="YES", size=Decimal("50"), status="closed",
        )
        db_session.add(trade_sell)
        await db_session.flush()

        order_sell = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade_sell.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="sell", outcome="YES",
            size=Decimal("50"), price=Decimal("0.65"),
            filled_size=Decimal("50"), filled_price=Decimal("0.65"),
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order_sell)
        await db_session.flush()

        fill_sell = Fill(
            exchange_order_id=order_sell.id, trade_id=trade_sell.id,
            market_id=market_id, fill_num=1,
            side="sell", outcome="YES",
            size=Decimal("50"), price=Decimal("0.65"),
            fee=Decimal("0.05"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill_sell)
        await db_session.flush()

        svc = PnLService(db_session)
        results = await svc.compute_realized_pnl(market_id=market_id)

        assert len(results) == 1
        result = results[0]
        expected_gross = (50 * 0.65) - 0.05
        expected_cost = (50 * 0.55) + 0.05
        expected_pnl = expected_gross - expected_cost
        assert result["realized_pnl"] == pytest.approx(expected_pnl, rel=1e-3)

    @pytest.mark.asyncio
    async def test_portfolio_pnl_uses_fills_only(self, db_session):
        svc = PnLService(db_session)
        portfolio = await svc.get_portfolio_pnl()
        assert "total_realized_pnl" in portfolio
        assert "total_unrealized_pnl" in portfolio
        assert "total_pnl" in portfolio


class TestOrderStateTransitions:
    """ExchangeOrder lifecycle mapping must be correct."""

    @pytest.mark.asyncio
    async def test_order_state_view_basic(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("100"), filled_price=Decimal("0.55"),
            retry_count=0,
            idempotency_key=str(uuid.uuid4()),
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(order)
        await db_session.flush()

        svc = OrderStateService(db_session)
        view = await svc.get_order_view(order.id)
        assert view is not None
        assert view.order_id == str(order.id)
        assert view.status == "filled"
        assert view.filled_pct == 100.0
        assert view.size == 100.0
        assert view.filled_size == 100.0

    @pytest.mark.asyncio
    async def test_order_state_partial_fill(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="partially_filled", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("30"), filled_price=Decimal("0.55"),
            retry_count=0,
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=order.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("30"), price=Decimal("0.55"),
            fee=Decimal("0.03"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        svc = OrderStateService(db_session)
        view = await svc.get_order_view(order.id)
        assert view is not None
        assert view.status == "partially_filled"
        assert view.filled_pct == 30.0

    @pytest.mark.asyncio
    async def test_trade_orders_list(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        o1 = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("25"), price=Decimal("0.55"),
            filled_size=Decimal("25"), filled_price=Decimal("0.55"),
            retry_count=0, idempotency_key=str(uuid.uuid4()),
        )
        o2 = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=2,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="sell", outcome="YES",
            size=Decimal("25"), price=Decimal("0.65"),
            filled_size=Decimal("25"), filled_price=Decimal("0.65"),
            retry_count=0, idempotency_key=str(uuid.uuid4()),
        )
        db_session.add_all([o1, o2])
        await db_session.flush()

        svc = OrderStateService(db_session)
        views = await svc.get_trade_orders(trade.id)
        assert len(views) == 2
        assert views[0].order_id == str(o1.id)
        assert views[1].order_id == str(o2.id)


class TestDriftDetection:
    """Drift detection must identify mismatches correctly."""

    @pytest.mark.asyncio
    async def test_drift_detection_missing_fill(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("50"), filled_price=Decimal("0.55"),
            retry_count=1,
            idempotency_key=str(uuid.uuid4()),
            submitted_at=datetime.now(timezone.utc),
        )
        db_session.add(order)
        await db_session.flush()

        svc = DriftDetectionService(db_session)

        clob_state = {
            "status": "FILLED",
            "filledSize": 100.0,
            "avgFillPrice": 0.56,
        }

        report = await svc.detect_order_drift(order, clob_state=clob_state)
        assert report["drift_detected"] is True
        issue_types = {i["type"] for i in report["issues"]}
        assert "status_mismatch" in issue_types
        assert "size_mismatch" in issue_types

    @pytest.mark.asyncio
    async def test_drift_no_issues_when_aligned(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="paper", exchange="polymarket_clob",
            status="filled", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("100"), filled_price=Decimal("0.55"),
            retry_count=0,
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        svc = DriftDetectionService(db_session)
        clob_state = {"status": "filled", "filledSize": 100.0}
        report = await svc.detect_order_drift(order, clob_state=clob_state)
        assert report["drift_detected"] is False

    @pytest.mark.asyncio
    async def test_position_drift_detected(self, db_session):
        market_id = uuid.uuid4()

        position = Position(
            market_id=market_id,
            direction="BUY",
            size=100.0,
            entry_price=0.55,
            current_price=0.55,
            status="OPEN",
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(position)
        await db_session.flush()

        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="open",
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
            fee=Decimal("0.05"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        svc = DriftDetectionService(db_session)
        report = await svc.detect_position_drift(position)
        assert report["drift_detected"] is True
        assert "position_size_mismatch" in {i["type"] for i in report["issues"]}


class TestEventStreamService:
    """EventStreamService must publish fill events without mutation."""

    @pytest.mark.asyncio
    async def test_publish_fill_event_no_mutation(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="open",
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
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            fee=Decimal("0.05"), filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        svc = EventStreamService()
        with patch("app.services.monitoring.event_stream_service.EventBus.publish", new=AsyncMock()) as mock_publish:
            await svc.publish_fill_event(fill)
            mock_publish.assert_called_once()
            args = mock_publish.call_args[0]
            assert args[0] == "trade:execution"
            assert args[1] == "fill.created"

        await db_session.refresh(fill)
        assert fill.side == "buy"


class TestApiMonitoringReadOnly:
    """Monitoring API endpoints must never mutate execution state."""

    @pytest.mark.asyncio
    async def test_metrics_service_is_read_only(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        svc = ExecutionMetricsService(db_session)
        metrics = await svc.get_trade_metrics(trade.id)

        result = await db_session.execute(select(Trade).where(Trade.id == trade.id))
        loaded = result.scalar_one()
        assert loaded.filled_size == 0
        assert loaded.filled_price is None
