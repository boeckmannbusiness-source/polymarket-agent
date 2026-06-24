import time
from typing import Dict, Optional, List
from app.domain.wallet.session import WalletSession, EphemeralWallet
from app.domain.wallet.models import WalletCapabilityState
from app.services.wallet.ephemeral_provider import EphemeralWalletProvider


class WalletSessionManager:
    """
    Manages the lifecycle of ephemeral wallet sessions.
    Enforces TTL and ensures key material destruction.
    """

    def __init__(
        self,
        provider: EphemeralWalletProvider,
        max_session_minutes: int = 30
    ):
        self._provider = provider
        self.max_session_ttl = max_session_minutes * 60
        self._sessions: Dict[str, WalletSession] = {}

    async def create_session(
        self,
        capabilities: List[WalletCapabilityState] = [WalletCapabilityState.SIMULATION_ONLY]
    ) -> WalletSession:
        """Creates a new session with an ephemeral wallet."""
        address = await self._provider.generate_keypair()
        # We don't actually need to store the private key in WalletSession
        # but the domain model currently has it in EphemeralWallet.
        # For security, we'll keep it only in the provider's memory.
        # But to satisfy the model, we'll use a placeholder or the actual bytes
        # if the domain model requires it for something.
        # Given the requirements, keys should only be in provider's memory.

        # Let's adjust EphemeralWallet in domain if needed, or just pass dummy bytes.
        # Actually, EphemeralWallet has private_key: bytes = Field(exclude=True)
        # To be safe and compliant with "keys in memory only", we'll keep them
        # ONLY in EphemeralWalletProvider._keys.

        session = WalletSession(
            wallet=EphemeralWallet(address=address, private_key=b""), # Key stays in provider
            expires_at=time.time() + self.max_session_ttl,
            capabilities=capabilities
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[WalletSession]:
        """Retrieves a session if it exists and is not expired."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.is_expired():
            self.destroy_session(session_id)
            return None

        if session.destroyed:
            return None

        return session

    def destroy_session(self, session_id: str):
        """Explicitly destroys a session and wipes its key material."""
        session = self._sessions.get(session_id)
        if session:
            self._provider.destroy(session.wallet.address)
            session.destroyed = True
            # We can also remove it from our dict
            del self._sessions[session_id]

    def cleanup_expired(self):
        """Cleans up all expired sessions."""
        now = time.time()
        expired_ids = [
            sid for sid, s in self._sessions.items()
            if s.expires_at < now or s.destroyed
        ]
        for sid in expired_ids:
            self.destroy_session(sid)

    def validate_session_for_signing(self, session_id: str) -> bool:
        """Returns True if the session is active and has SIGN_ONLY capability."""
        session = self.get_session(session_id)
        if not session:
            return False

        return WalletCapabilityState.SIGN_ONLY in session.capabilities
