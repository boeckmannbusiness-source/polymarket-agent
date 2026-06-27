import pytest
import time
from app.domain.wallet.models import SignedArtifact
from app.services.wallet.policy import SignedArtifactPolicy
from app.services.wallet.signing_sandbox import SigningSandbox
from app.services.wallet.session.manager import WalletSessionManager
from app.services.wallet.ephemeral_provider import EphemeralWalletProvider
from app.services.execution.governance.execution_governor import ExecutionGovernor
from app.domain.execution_authorization.models import ExecutionMode

def test_signed_artifact_serialization_forbidden():
    """Prove that SignedArtifact cannot be serialized."""
    artifact = SignedArtifact(
        signature="test_sig",
        wallet_address="test_addr",
        timestamp=time.time()
    )

    with pytest.raises(PermissionError) as excinfo:
        artifact.model_dump()
    assert "Serialization of SignedArtifact is forbidden" in str(excinfo.value)

    with pytest.raises(PermissionError) as excinfo:
        artifact.model_dump_json()
    assert "Serialization of SignedArtifact is forbidden" in str(excinfo.value)

def test_signed_artifact_policy_expiry():
    """Prove that SignedArtifactPolicy enforces transience."""
    expired_artifact = SignedArtifact(
        signature="test_sig",
        wallet_address="test_addr",
        timestamp=time.time() - 61 # Over 60s
    )

    with pytest.raises(PermissionError) as excinfo:
        SignedArtifactPolicy.validate_usage(expired_artifact)
    assert "transient window expired" in str(excinfo.value)

@pytest.mark.asyncio
async def test_signing_sandbox_returns_artifact():
    """Prove that SigningSandbox returns the hardened artifact."""
    provider = EphemeralWalletProvider()
    manager = WalletSessionManager(provider)
    governor = ExecutionGovernor(ExecutionMode.SANDBOX)
    sandbox = SigningSandbox(manager, provider, governor)

    # Setup session
    from app.domain.wallet.models import WalletCapabilityState
    session = await manager.create_session(capabilities=[WalletCapabilityState.SIGN_ONLY])
    session_id = session.session_id

    artifact = await sandbox.sign_transaction(session_id, "test_payload")

    assert isinstance(artifact, SignedArtifact)
    assert artifact.signature is not None
    assert artifact.wallet_address == session.wallet.address

    # Ensure it's not serializable
    with pytest.raises(PermissionError):
        artifact.model_dump()

def test_policy_forbids_export_replay():
    """Prove explicit policy prohibitions."""
    with pytest.raises(PermissionError):
        SignedArtifactPolicy.forbid_export()

    with pytest.raises(PermissionError):
        SignedArtifactPolicy.forbid_replay()
