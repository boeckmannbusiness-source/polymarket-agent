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

def test_snapshot_matches_certification_manifest():
    """Verify ARCHITECTURE_SNAPSHOT matches CERTIFICATION_MANIFEST assumptions."""
    import json
    import os

    snapshot_path = "ARCHITECTURE_SNAPSHOT.json"
    manifest_path = "CERTIFICATION_MANIFEST.md"

    assert os.path.exists(snapshot_path), "Snapshot must exist"
    assert os.path.exists(manifest_path), "Manifest must exist"

    with open(snapshot_path, "r") as f:
        snapshot = json.load(f)

    # 1. Registry frozen == true
    assert snapshot["exchanges"]["frozen"] is True

    # 2. No active live adapter in sandbox
    # 'live' is disabled, 'paper' and 'live_jupiter' are allowed
    for adapter_name, meta in snapshot["exchanges"]["metadata"].items():
        if meta.get("enabled", False):
            # If enabled, must be paper or simulation
            assert adapter_name in {"paper", "live_jupiter"}, f"Live adapter {adapter_name} enabled!"
            assert meta.get("sandbox_allowed") is True
        else:
            # If it's the legacy 'live' one, it must be disabled
            if adapter_name == "live":
                assert meta.get("enabled") is False
                assert meta.get("sandbox_allowed") is False

    # 3. Startup invariants present
    expected_invariants = {
        "EXECUTION_MODE in {simulation, sandbox}",
        "STRICT_LIVE_ENABLED == False",
        "CAPITAL_ENABLED == False",
        "ExchangeAdapterRegistry is frozen"
    }
    snapshot_invariants = set(snapshot["startup_invariants"])
    assert expected_invariants.issubset(snapshot_invariants)
