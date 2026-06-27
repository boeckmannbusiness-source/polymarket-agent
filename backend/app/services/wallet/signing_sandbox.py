import time
from typing import Optional, Any
from app.services.wallet.session.manager import WalletSessionManager
from app.services.wallet.ephemeral_provider import EphemeralWalletProvider
from app.services.execution.governance.execution_governor import ExecutionGovernor
from app.domain.wallet.models import SignedArtifact
from app.services.wallet.policy import SignedArtifactPolicy


class SigningSandbox:
    """
    Signing Sandbox ensures that signing operations are isolated
    from broadcast/execution paths.
    """

    def __init__(
        self,
        session_manager: WalletSessionManager,
        provider: EphemeralWalletProvider,
        governor: ExecutionGovernor
    ):
        self._session_manager = session_manager
        self._provider = provider
        self._governor = governor

    async def sign_transaction(self, session_id: str, payload: str) -> SignedArtifact:
        """
        Signs a transaction payload if the session is valid.
        Returns a transient SignedArtifact.
        """
        if not self._session_manager.validate_session_for_signing(session_id):
            raise PermissionError("Session is invalid or does not have signing capabilities")

        session = self._session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Authorize through governor
        self._governor.authorize_sign({"wallet_address": session.wallet.address})

        # Perform local signing
        signature = await self._provider.sign(payload, session.wallet.address)

        artifact = SignedArtifact(
            signature=signature,
            wallet_address=session.wallet.address,
            timestamp=time.time()
        )

        # Enforce no persistence policy
        SignedArtifactPolicy.forbid_persistence(artifact)

        return artifact

    async def simulate_transaction(self, session_id: str, payload: str) -> Any:
        """
        Simulates a transaction. Isolated from broadcast.
        """
        # This would call the RPC Reader's simulate_transaction
        # For now, it represents a sandbox-allowed boundary.
        pass

    def send_transaction(self, *args, **kwargs):
        """Forbidden in Sandbox."""
        raise PermissionError("send_transaction is forbidden in SigningSandbox")

    def broadcast(self, *args, **kwargs):
        """Forbidden in Sandbox."""
        raise PermissionError("broadcast is forbidden in SigningSandbox")

    def submit(self, *args, **kwargs):
        """Forbidden in Sandbox."""
        raise PermissionError("submit is forbidden in SigningSandbox")
