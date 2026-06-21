import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy import select

from app.models import Trade, ExchangeOrder, Fill, Position
from app.services.execution.execution_service import ExecutionService
from app.services.execution.fill_ingestion_service import FillIngestionService
from app.services.execution.fill_handler import FillHandler
from app.services.execution.reconciliation_service import ReconciliationService
from app.services.capabilities import capability_registry
from app.domain.capabilities import VenueCapabilities, VenueCapability


@pytest.fixture(autouse=True)
def setup_live_capabilities():
    capability_registry.register("live", VenueCapabilities(
        venue="live",
        supports={
            VenueCapability.QUOTE,
            VenueCapability.ROUTING,
            VenueCapability.TRANSACTION_BUILDING,
            VenueCapability.EXECUTION,
        }
    ))


class TestLiveOrderSubmissionIdempotent:
    """Same idempotency_key cannot create duplicate orders."""

    @pytest.mark.asyncio
    async def test_submit_order_idempotent_skip(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_asset_id="asset_123",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        service = ExecutionService(db_session)

        with patch.object(service, "_get_adapter", new=AsyncMock()) as mock_factory:
            await service.submit_order(order)
            mock_factory.assert_not_called()

        assert order.status == "submitted"

    @pytest.mark.asyncio
    async def test_execution_service_skips_submitted_orders(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_asset_id="asset_123",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(order)
        await db_session.flush()

        service = ExecutionService(db_session)

        with patch.object(service, "_get_adapter", new=AsyncMock()) as mock_factory:
            await service.submit_order(order)
            mock_factory.assert_not_called()

        assert order.status == "submitted"


class TestCLOBFillIngestionCreatesFill:
    """External fill events must create Fill rows via FillIngestionService."""

    @pytest.mark.asyncio
    async def test_ingest_creates_fill(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            clob_order_id="clob-001",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        clob_event = {
            "id": "clob-fill-001",
            "order_id": "clob-001",
            "side": "BUY",
            "size": "50.0",
            "price": "0.55",
            "fee": "0.05",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        svc = FillIngestionService(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock()):
            await svc.ingest_clob_fills([clob_event])

        fills = await db_session.execute(
            select(Fill).where(Fill.exchange_order_id == exchange_order.id)
        )
        fill_list = list(fills.scalars().all())
        assert len(fill_list) == 1
        assert fill_list[0].clob_fill_id == "clob-fill-001"
        assert fill_list[0].size == Decimal("50.0")

    @pytest.mark.asyncio
    async def test_ingest_updates_exchange_order(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            clob_order_id="clob-002",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        clob_event = {
            "id": "clob-fill-002",
            "order_id": "clob-002",
            "side": "BUY",
            "size": "100.0",
            "price": "0.55",
            "fee": "0.10",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        svc = FillIngestionService(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock()):
            await svc.ingest_clob_fills([clob_event])

        await db_session.refresh(exchange_order)
        assert exchange_order.status == "filled"
        assert exchange_order.filled_size == Decimal("100")
        assert exchange_order.filled_price == Decimal("0.55")


class TestFillDeduplication:
    """Duplicate clob_fill_id must be ignored."""

    @pytest.mark.asyncio
    async def test_duplicate_fill_id_skipped(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_order_id="clob-003",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=exchange_order.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_fill_id="clob-fill-003",
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        clob_event = {
            "id": "clob-fill-003",
            "order_id": "clob-003",
            "side": "BUY",
            "size": "50.0",
            "price": "0.55",
            "fee": "0.05",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        svc = FillIngestionService(db_session)
        with patch.object(FillHandler, "process_fill", new=AsyncMock()):
            await svc.ingest_clob_fills([clob_event])

        fills = await db_session.execute(
            select(Fill).where(Fill.exchange_order_id == exchange_order.id)
        )
        fill_list = list(fills.scalars().all())
        assert len(fill_list) == 1


class TestPositionUpdatesFromLiveFill:
    """Fill from CLOB ingestion must update Position."""

    @pytest.mark.asyncio
    async def test_position_created_from_live_fill(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("50"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_order_id="clob-004",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        clob_event = {
            "id": "clob-fill-004",
            "order_id": "clob-004",
            "side": "BUY",
            "size": "50.0",
            "price": "0.55",
            "fee": "0.05",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        svc = FillIngestionService(db_session)
        await svc.ingest_clob_fills([clob_event])

        positions = await db_session.execute(
            select(Position).where(Position.market_id == market_id)
        )
        pos_list = list(positions.scalars().all())
        assert len(pos_list) == 1
        assert pos_list[0].direction == "BUY"
        assert pos_list[0].size == 50.0


class TestNoTradeMutationInLiveFlow:
    """Trade must remain unchanged after full live flow."""

    @pytest.mark.asyncio
    async def test_trade_unchanged_after_fill_ingestion(self, db_session):
        market_id = uuid.uuid4()
        trade = Trade(
            id=uuid.uuid4(), market_id=market_id,
            side="buy", outcome="YES", size=Decimal("100"),
            price=Decimal("0.55"), status="pending",
            filled_size=0, filled_price=None,
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            clob_order_id="clob-005",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        clob_event = {
            "id": "clob-fill-005",
            "order_id": "clob-005",
            "side": "BUY",
            "size": "100.0",
            "price": "0.55",
            "fee": "0.10",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        svc = FillIngestionService(db_session)
        await svc.ingest_clob_fills([clob_event])

        await db_session.refresh(trade)
        assert trade.filled_size == 0
        assert trade.filled_price is None
        assert trade.pnl is None or trade.pnl == 0


class TestReconciliationService:
    """ReconciliationService must detect drift between DB and CLOB state."""

    @pytest.mark.asyncio
    async def test_reconcile_missing_fills(self, db_session):
        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("100"), status="open",
        )
        db_session.add(trade)
        await db_session.flush()

        exchange_order = ExchangeOrder(
            id=uuid.uuid4(), trade_id=trade.id, order_num=1,
            engine_type="live", exchange="polymarket_clob",
            status="submitted", side="buy", outcome="YES",
            size=Decimal("100"), price=Decimal("0.55"),
            filled_size=Decimal("50"), filled_price=Decimal("0.55"),
            clob_order_id="clob-reconcile-001",
            idempotency_key=str(uuid.uuid4()),
        )
        db_session.add(exchange_order)
        await db_session.flush()

        fill = Fill(
            exchange_order_id=exchange_order.id, trade_id=trade.id,
            market_id=trade.market_id, fill_num=1,
            side="buy", outcome="YES",
            size=Decimal("50"), price=Decimal("0.55"),
            clob_fill_id="existing-fill",
            filled_at=datetime.now(timezone.utc),
        )
        db_session.add(fill)
        await db_session.flush()

        svc = ReconciliationService(db_session)

        clob_state = {
            "status": "FILLED",
            "filledSize": 100.0,
            "avgFillPrice": 0.55,
        }

        with patch.object(svc, "_get_client", new=AsyncMock()) as mock_client:
            mock_client.return_value.get_order = AsyncMock(return_value=clob_state)
            with patch.object(FillHandler, "process_fill", new=AsyncMock()):
                await svc.reconcile_order(exchange_order)

        await db_session.refresh(exchange_order)
        assert exchange_order.status == "filled"
        assert exchange_order.filled_size == Decimal("100")

        fills = await db_session.execute(
            select(Fill).where(Fill.exchange_order_id == exchange_order.id)
        )
        fill_list = list(fills.scalars().all())
        assert len(fill_list) == 2


class TestExecutionServiceLiveRouting:
    """ExecutionService must route to correct adapter based on engine_type."""

    @pytest.mark.asyncio
    async def test_live_routing_uses_polymarket_adapter(self, db_session):
        from app.exchanges.paper import PaperExchangeAdapter

        trade = Trade(
            id=uuid.uuid4(), market_id=uuid.uuid4(),
            side="buy", outcome="YES", size=Decimal("50"),
            trade_type="live", status="pending",
        )
        db_session.add(trade)
        await db_session.flush()

        service = ExecutionService(db_session)
        from app.exchanges import ExchangeAdapterRegistry
        from app.exchanges.polymarket_live import PolymarketLiveAdapter
        from app.domain.execution import ExecutionResult
        ExchangeAdapterRegistry.register("live", PolymarketLiveAdapter)

        mock_result = ExecutionResult(
            execution_id=str(uuid.uuid4()),
            adapter="live",
            status="submitted",
            latency_ms=100.0,
        )

        with patch("app.exchanges.polymarket_live.PolymarketLiveAdapter.submit_order", new=AsyncMock(return_value=mock_result)) as mock_submit:
            with patch.object(PaperExchangeAdapter, "submit_order", new=AsyncMock()) as mock_paper:
                with patch.object(FillHandler, "process_fill", new=AsyncMock()):
                    await service.create_trade_execution(trade)
                    mock_submit.assert_called_once()
                    mock_paper.assert_not_called()
