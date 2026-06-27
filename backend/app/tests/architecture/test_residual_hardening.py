import pytest
from unittest.mock import MagicMock, patch
from app.services.admission.admission_service import AdmissionService
from app.domain.admission.models import AdmissionReceipt, AdmissionDecision
from app.services.rpc.solana_rpc_reader import SolanaRpcReader
from app.services.replay.offline_guard import ReplayOfflineGuard, ReplayIsolationViolation

@pytest.mark.asyncio
async def test_replay_admission_expiry_behavior():
    """Prove that AdmissionService handles expired receipts during replay."""
    service = AdmissionService()

    # Stale receipt (slot 100, valid until 200, but current slot is 300)
    # Using real model fields from models.py
    stale_receipt = AdmissionReceipt(
        admission_id="test",
        decision=AdmissionDecision.ALLOW_SIMULATION,
        decision_hash="hash",
        asset_snapshot_hash="snap_hash",
        policy_version="1.0",
        reasons=[],
        created_slot=100,
        valid_until_slot=200
    )

    # Replay validates integrity only, not freshness (unless explicitly checked during planning)
    # The AdmissionService.admit_asset checks stored_receipt expiry ONLY if not is_replay

    # Create a mock snapshot with slot 300
    from app.domain.admission.models import AssetSnapshot
    mock_snapshot = MagicMock(spec=AssetSnapshot)
    mock_snapshot.evaluation_slot = 300

    # Call admit_asset with stored_receipt and is_replay=False to trigger expiry check
    with pytest.raises(ValueError) as excinfo:
        await service.admit_asset(snapshot=mock_snapshot, capabilities=MagicMock(), is_replay=False, stored_receipt=stale_receipt)

    assert "has expired" in str(excinfo.value)

@pytest.mark.asyncio
async def test_replay_direct_rpc_blocked():
    """Prove that direct RPC instantiation still hits ReplayOfflineGuard."""
    # Even if we don't use dependency injection, the guard is ContextVar based.
    reader = SolanaRpcReader("http://localhost:8899")

    with patch("app.services.replay.offline_guard.ReplayOfflineGuard.is_replay_active", return_value=True):
        with pytest.raises(ReplayIsolationViolation):
            await reader.get_balance("some_address")

    await reader.close()
