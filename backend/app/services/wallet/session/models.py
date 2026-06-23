import uuid
import time
from typing import Optional, Dict
from pydantic import BaseModel, Field


class EphemeralWallet(BaseModel):
    """Runtime-only wallet. Never persisted."""
    address: str
    private_key: bytes = Field(exclude=True) # Exclude from serialization


class WalletSession(BaseModel):
    """Represents a temporary wallet session."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wallet: EphemeralWallet
    created_at: float = Field(default_factory=time.time)
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class WalletLifecycle:
    """Manages the lifecycle of ephemeral wallet sessions."""

    def __init__(self, ttl_seconds: int = 3600):
        self._sessions: Dict[str, WalletSession] = {}
        self.ttl = ttl_seconds

    def create_session(self, address: str, private_key: bytes) -> WalletSession:
        """Creates a new ephemeral session."""
        expires_at = time.time() + self.ttl
        session = WalletSession(
            wallet=EphemeralWallet(address=address, private_key=private_key),
            expires_at=expires_at
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[WalletSession]:
        """Retrieves a session if it exists and is not expired."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            self.destroy_session(session_id)
            return None
        return session

    def destroy_session(self, session_id: str):
        """Explicitly destroys a session and wipes its state."""
        if session_id in self._sessions:
            # In a real environment, we might want to overwrite the memory
            # for the private key if possible in Python.
            del self._sessions[session_id]

    def cleanup_expired(self):
        """Cleans up all expired sessions."""
        now = time.time()
        expired_ids = [sid for sid, s in self._sessions.items() if s.expires_at < now]
        for sid in expired_ids:
            self.destroy_session(sid)
