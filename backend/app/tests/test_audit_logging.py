import pytest
from unittest.mock import AsyncMock, patch

from app.services.audit.audit_logger import emit, audit_context, _trade_id, _order_id, _fill_id, _incident_id, _strategy_id


class TestAuditLogger:
    @pytest.fixture(autouse=True)
    def mock_redis(self):
        with patch("app.redis.get_redis", new=AsyncMock(side_effect=RuntimeError("No Redis in test"))):
            yield

    async def test_emit_succeeds(self):
        await emit("test.event", "test_entity", "entity_123", {"key": "value"})

    async def test_emit_never_raises(self):
        await emit("test.event", "test_entity", "entity_123", {"key": "value"})

    async def test_audit_context_sets_and_resets(self):
        assert _trade_id.get() == ""
        with audit_context(trade_id="trade_123"):
            assert _trade_id.get() == "trade_123"
            with audit_context(order_id="order_456"):
                assert _trade_id.get() == "trade_123"
                assert _order_id.get() == "order_456"
            assert _order_id.get() == ""
        assert _trade_id.get() == ""

    async def test_audit_context_resets_on_exception(self):
        assert _trade_id.get() == ""
        try:
            with audit_context(trade_id="trade_789"):
                raise ValueError("boom")
        except ValueError:
            pass
        assert _trade_id.get() == ""

    async def test_emit_with_context(self):
        with audit_context(trade_id="trade_abc", strategy_id="strat_xyz"):
            await emit("test.with_context", "test", "id_1", {"key": "value"})

    async def test_correlation_id_propagates(self):
        with patch("app.services.audit.audit_logger._correlation_id") as mock_cid:
            mock_cid.get.return_value = "corr_001"
            await emit("test.correlation", "test", "id_1", {"key": "value"})
            mock_cid.get.assert_called()
