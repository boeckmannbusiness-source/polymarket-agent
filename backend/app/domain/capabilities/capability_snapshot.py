from pydantic import BaseModel
from typing import Optional
from app.domain.wallet.models import WalletCapabilityState


class CapabilitySnapshot(BaseModel):
    """Snapshot of system capabilities during execution."""
    execution_mode: str
    rpc_permissions: list[str]
    simulation_enabled: bool
    signing_enabled: bool
    broadcast_enabled: bool
    wallet_capability: Optional[WalletCapabilityState] = None
