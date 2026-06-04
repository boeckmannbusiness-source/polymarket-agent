import uuid
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models import ExchangeOrder, Trade, Fill
from app.services.recovery.order_recovery_service import OrderRecoveryService


class TestOrderRecovery:
    @pytest.fixture(autouse=True)
    def setup_method(self, db_session):
        self.db = db_session
        self.svc = OrderRecoveryService(self.db)

    @pytest.fixture(autouse=True)
    def mock_redis(self):
        with patch.object(OrderRecoveryService, "_safe_redis", return_value=None):
            yield

    async def _create_trade(self, db, side="buy", outcome="YES", size=Decimal("10"), price=Decimal("0.5")):
        trade = Trade(
            side=side,
            outcome=outcome,
            size=size,
            price=price,
            agent_id="test_agent",
            market_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        db.add(trade)
        await db.flush()
        return trade

    async def _create_order(self, db, trade, status="pending", engine_type="paper", clob_order_id=None, retry_count=0, submitted_at=None):
        order = ExchangeOrder(
            trade_id=trade.id,
            order_num=1,
            engine_type=engine_type,
            exchange="polymarket_clob",
            status=status,
            side=trade.side,
            outcome=trade.outcome,
            size=trade.size,
            price=trade.price,
            idempotency_key=f"ik_{trade.id}_{status}",
            retry_count=retry_count,
            submitted_at=submitted_at or datetime.now(timezone.utc) - timedelta(hours=2),
            clob_order_id=clob_order_id,
        )
        db.add(order)
        await db.flush()
        return order

    async def test_scan_empty_returns_zero(self):
        report = await self.svc.run_scan(force=True)
        assert report["orders_scanned"] == 0
        assert report["orders_recovered"] == 0
        assert report["incidents_created"] == 0
        assert report["abandoned_orders"] == 0

    async def test_scan_skips_filled_orders(self):
        trade = await self._create_trade(self.db)
        order = await self._create_order(self.db, trade, status="filled", submitted_at=datetime.now(timezone.utc) - timedelta(hours=4))
        report = await self.svc.run_scan(force=True)
        assert report["orders_scanned"] == 0

    async def test_scan_detects_stuck_pending_order(self):
        trade = await self._create_trade(self.db)
        order = await self._create_order(self.db, trade, status="pending", submitted_at=datetime.now(timezone.utc) - timedelta(hours=4))
        report = await self.svc.run_scan(force=True)
        assert report["orders_scanned"] == 1

    async def test_scan_abandons_high_retry_count(self):
        trade = await self._create_trade(self.db)
        order = await self._create_order(self.db, trade, status="submitted", retry_count=5, submitted_at=datetime.now(timezone.utc) - timedelta(hours=4))
        with patch("app.services.recovery.order_recovery_service.emit", new=AsyncMock()):
            report = await self.svc.run_scan(force=True)
        assert report["abandoned_orders"] == 1
        assert order.status == "cancelled"
        assert order.last_error == "abandoned_by_recovery"

    async def test_scan_reconciles_live_order(self):
        trade = await self._create_trade(self.db)
        order = await self._create_order(self.db, trade, status="submitted", engine_type="live", clob_order_id="clob_123", submitted_at=datetime.now(timezone.utc) - timedelta(hours=4))

        mock_recon = AsyncMock()
        mock_recon.reconcile_order = AsyncMock()
        svc = OrderRecoveryService(self.db, reconciliation_svc=mock_recon)
        with patch("app.services.recovery.order_recovery_service.emit", new=AsyncMock()):
            report = await svc.run_scan(force=True)

        assert report["orders_scanned"] == 1
        mock_recon.reconcile_order.assert_called_once()

    async def test_scan_creates_incident_on_reconcile_fail(self):
        trade = await self._create_trade(self.db)
        order = await self._create_order(self.db, trade, status="submitted", engine_type="live", clob_order_id="clob_456", submitted_at=datetime.now(timezone.utc) - timedelta(hours=4))

        mock_recon = AsyncMock()
        mock_recon.reconcile_order = AsyncMock(side_effect=Exception("CLOB unavailable"))
        svc = OrderRecoveryService(self.db, reconciliation_svc=mock_recon)

        with patch("app.services.recovery.order_recovery_service.incident_service.create_from_alert", new=AsyncMock()):
            with patch("app.services.recovery.order_recovery_service.emit", new=AsyncMock()):
                report = await svc.run_scan(force=True)

        assert report["incidents_created"] == 1
