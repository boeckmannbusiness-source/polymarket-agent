import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.execution.execution_service import ExecutionService
from app.services.rpc.solana_rpc_reader import SolanaRpcReader
from app.services.trade_service import TradeService
from app.services.event_bridge import EventPersistenceBridge
from app.services.execution.governance.execution_governor import ExecutionAuthorizationError
from app.services.replay.offline_guard import ReplayOfflineGuard, ReplayIsolationViolation

@pytest.mark.asyncio
async def test_execution_exception_propagates():
    """Prove that ExecutionAuthorizationError propagates through ExecutionService."""
    db = MagicMock()
    service = ExecutionService(db)

    # Mock governor to raise error
    service._governor.authorize_execution = MagicMock(side_effect=ExecutionAuthorizationError("Blocked"))

    with pytest.raises(ExecutionAuthorizationError):
        await service._check_safety(trace_id="test")

@pytest.mark.asyncio
async def test_broadcast_exception_propagates():
    """Prove that PermissionError (broadcast attempt) propagates through RPC layer."""
    reader = SolanaRpcReader("https://api.mainnet-beta.solana.com")

    # payload with forbidden method
    payload = {"method": "sendTransaction"}

    with pytest.raises(PermissionError):
        await reader._post(payload)

    await reader.close()

@pytest.mark.asyncio
async def test_replay_exception_propagates():
    """Prove that ReplayIsolationViolation propagates through RPC layer."""
    reader = SolanaRpcReader("https://api.mainnet-beta.solana.com")

    with patch("app.services.replay.offline_guard.ReplayOfflineGuard.is_replay_active", return_value=True):
        with pytest.raises(ReplayIsolationViolation):
            await reader._post({"method": "getBalance"})

    await reader.close()

@pytest.mark.asyncio
async def test_trade_service_safety_propagation():
    """Prove that safety exceptions propagate through TradeService."""
    db = MagicMock()
    service = TradeService(db)

    # Using a different patch target that exists and is called within the try block
    with patch("app.services.trade_service.json.loads", side_effect=PermissionError("Safety violation")):
        # We need a mocked redis response to reach json.loads
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value="{}")

        with patch("app.redis.get_redis", return_value=mock_redis):
            with pytest.raises(PermissionError):
                from app.schemas.trade import TradeCreateRequest
                # We also need to mock get_mode_manager
                with patch("app.core.system_mode.get_mode_manager") as mock_mgr:
                    mock_mgr.return_value.is_shadow.return_value = False
                    import uuid
                    await service.create_trade(TradeCreateRequest(
                        market_id=uuid.uuid4(), side="buy", outcome="YES", size=1.0
                    ))

@pytest.mark.asyncio
async def test_event_bridge_safety_propagation():
    """Prove that safety exceptions propagate through EventPersistenceBridge."""
    bridge = EventPersistenceBridge()

    with patch.object(bridge, "_persist_normalized_event", side_effect=ExecutionAuthorizationError("Blocked")):
        with pytest.raises(ExecutionAuthorizationError):
            await bridge._persist_with_retry({"event_type": "trade", "data": {"test": True}})
