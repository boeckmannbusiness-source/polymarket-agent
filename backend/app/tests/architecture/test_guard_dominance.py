import pytest
from unittest.mock import MagicMock, patch
from app.services.execution.execution_service import ExecutionService
from app.services.execution.governance.execution_governor import ExecutionAuthorizationError
from app.services.capital.guard import CapitalGuard
from app.domain.capital.models import CapitalDecision, RiskReceipt
from app.domain.execution_authorization.models import ExecutionMode

@pytest.mark.asyncio
async def test_execution_requires_governor():
    """Prove that ExecutionService cannot submit intent without governor approval."""
    db = MagicMock()
    # By default ExecutionService uses settings.EXECUTION_MODE, let's assume it is 'simulation'
    service = ExecutionService(db)

    # Mock governor to DENY
    with patch.object(service._governor, "authorize_execution", side_effect=ExecutionAuthorizationError("Denied by test")):
        intent = MagicMock()
        intent.instrument.venue = "paper"

        with pytest.raises(ExecutionAuthorizationError):
            await service.submit_intent(intent)

def test_guard_cannot_be_bypassed():
    """Prove that CapitalGuard dominates even if Governor/Policy allowed it."""
    # Guard with capital_enabled = False (The certification invariant)
    guard = CapitalGuard(capital_enabled=False)

    # Mock receipt that was ALLOWED by Policy
    receipt = RiskReceipt(
        risk_id="test",
        capital_decision=CapitalDecision.ALLOW,
        policy_version="1.0",
        risk_snapshot={},
        reason_codes=[],
        created_slot=100,
        valid_until_slot=200,
        risk_hash="old_hash"
    )

    # Enforce guard
    secured_receipt = guard.enforce(receipt)

    assert secured_receipt.capital_decision == CapitalDecision.BLOCK
    assert "CAPITAL_DISABLED" in secured_receipt.reason_codes
    assert secured_receipt.risk_hash != "old_hash" # Must be recalculated

@pytest.mark.asyncio
async def test_governor_dominance_structural():
    """Structural proof that ExecutionService calls governor before adapter."""
    db = MagicMock()
    service = ExecutionService(db)

    intent = MagicMock()
    intent.instrument.venue = "paper"

    # We mock _validate_capabilities and _check_safety which are called before adapter
    with patch.object(service, "_governor") as mock_gov:
        with patch.object(service, "_get_adapter") as mock_adapter_getter:
            # We also need to mock _validate_capabilities as it calls resolver which might use global settings
            with patch.object(service, "_validate_capabilities", return_value=None):

                # Simpler check: If gov raises, adapter is never called.
                mock_gov.authorize_execution.side_effect = ExecutionAuthorizationError("Stop")

                with pytest.raises(ExecutionAuthorizationError):
                    await service.submit_intent(intent)

                mock_adapter_getter.assert_not_called()
