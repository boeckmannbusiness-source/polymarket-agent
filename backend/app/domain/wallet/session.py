import uuid
import time
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, ConfigDict
from app.domain.wallet.models import WalletCapabilityState


class EphemeralWallet(BaseModel):
    """Runtime-only wallet. Never persisted."""
    address: str
    private_key: bytes = Field(exclude=True) # Exclude from serialization

    model_config = ConfigDict(extra="forbid")


class WalletSession(BaseModel):
    """Represents a temporary wallet session."""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    wallet: EphemeralWallet
    created_at: float = Field(default_factory=time.time)
    expires_at: float
    capabilities: List[WalletCapabilityState] = []
    destroyed: bool = False

    def is_expired(self) -> bool:
        return time.time() > self.expires_at
