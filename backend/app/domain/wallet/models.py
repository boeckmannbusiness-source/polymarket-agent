from enum import Enum
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class WalletCapabilityState(str, Enum):
    NO_WALLET = "NO_WALLET"
    SIMULATION_ONLY = "SIMULATION_ONLY"
    SIGN_ONLY = "SIGN_ONLY"


class WalletIdentity(BaseModel):
    address: str
    label: str
    venue: str
    metadata: Optional[dict] = None


class WalletCapability(BaseModel):
    venue: str
    can_sign: bool = False
    can_simulate: bool = True
    supported_assets: List[str] = []


class WalletBalance(BaseModel):
    address: str
    asset_symbol: str
    amount: Decimal
    last_updated: Optional[float] = None


class WalletTransaction(BaseModel):
    transaction_id: str
    wallet_address: str
    venue: str
    amount: Decimal
    asset_symbol: str
    status: str  # pending, confirmed, failed
    timestamp: float
    metadata: Optional[dict] = None


class WalletReceipt(BaseModel):
    """Replay-compatible receipt of wallet activity."""
    wallet_session_id: str
    capability_state: WalletCapabilityState
    signature_metadata: Optional[dict] = None
    destroyed_at: Optional[float] = None
