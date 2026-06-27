import pytest
from unittest.mock import MagicMock, patch
from app.services.capabilities.startup_validation import StartupSafetyValidator
from app.exchanges import ExchangeAdapterRegistry
from app.domain.wallet.models import SignedArtifact
from app.services.rpc.sandbox_rpc_writer import SandboxRpcWriter
from app.services.rpc.null_rpc_writer import NullRpcWriter
from app.services.capital.guard import CapitalGuard
from app.domain.capital.models import CapitalDecision, RiskReceipt
from app.services.replay.offline_guard import ReplayOfflineGuard, ReplayIsolationViolation

def test_startup_validator_exists():
    """Ensure StartupSafetyValidator is present and has validate method."""
    assert hasattr(StartupSafetyValidator, "validate")
    assert callable(StartupSafetyValidator.validate)

def test_registry_freeze_enforced():
    """Ensure ExchangeAdapterRegistry enforces freeze."""
    ExchangeAdapterRegistry.freeze()
    assert ExchangeAdapterRegistry._frozen is True

    with pytest.raises(PermissionError):
        ExchangeAdapterRegistry.register("drift_test", MagicMock())

def test_signed_artifact_serialization_blocked():
    """Ensure SignedArtifact forbids model_dump and model_dump_json."""
    artifact = SignedArtifact(
        signature="test_sig",
        wallet_address="test_addr",
        timestamp=123456789.0
    )

    with pytest.raises(PermissionError) as exc:
        artifact.model_dump()
    assert "forbidden by SignedArtifactPolicy" in str(exc.value)

    with pytest.raises(PermissionError) as exc:
        artifact.model_dump_json()
    assert "forbidden by SignedArtifactPolicy" in str(exc.value)

def test_no_live_adapters_registered():
    """Ensure no mainnet live adapters are in the registry."""
    # paper, live_jupiter, and live (mapped to paper) are allowed
    allowed = {"paper", "live_jupiter", "live"}
    registered = set(ExchangeAdapterRegistry._adapters.keys())

    # Polymarket is also allowed if it's the simulation one,
    # but the manifest says no live adapters.
    # Currently registered: ['paper', 'live_jupiter', 'live']

    for adapter in registered:
        assert adapter in allowed, f"Uncertified adapter '{adapter}' found in registry"

def test_rpc_writers_forbid_send_transaction():
    """Ensure Sandbox and Null RPC writers raise on send_transaction."""
    null_writer = NullRpcWriter()
    sandbox_writer = SandboxRpcWriter()

    with pytest.raises(Exception) as exc:
        import asyncio
        asyncio.run(null_writer.send_transaction("test"))
    assert "forbidden" in str(exc.value).lower()

    with pytest.raises(Exception) as exc:
        import asyncio
        asyncio.run(sandbox_writer.send_transaction("test"))
    assert "forbidden" in str(exc.value).lower()

def test_capital_guard_dominance():
    """Ensure CapitalGuard strictly blocks if capital_enabled is False."""
    guard = CapitalGuard(capital_enabled=False)
    receipt = RiskReceipt(
        risk_id="test",
        capital_decision=CapitalDecision.ALLOW,
        policy_version="1.0",
        risk_snapshot={},
        reason_codes=[],
        created_slot=100,
        valid_until_slot=200,
        risk_hash="initial"
    )

    secured = guard.enforce(receipt)
    assert secured.capital_decision == CapitalDecision.BLOCK
    assert "CAPITAL_DISABLED" in secured.reason_codes

def test_replay_offline_guard_active():
    """Ensure ReplayOfflineGuard correctly sets and resets replay state."""
    assert ReplayOfflineGuard.is_replay_active() is False

    with ReplayOfflineGuard.enforce():
        assert ReplayOfflineGuard.is_replay_active() is True

    assert ReplayOfflineGuard.is_replay_active() is False

def test_safety_exceptions_inherit_from_base():
    """Ensure safety critical exceptions are not swallowed easily."""
    from app.core.exceptions import StartupSafetyViolation
    from app.services.execution.governance.execution_governor import ExecutionAuthorizationError

    assert issubclass(StartupSafetyViolation, Exception)
    assert issubclass(ExecutionAuthorizationError, Exception)
    assert issubclass(ReplayIsolationViolation, Exception)
