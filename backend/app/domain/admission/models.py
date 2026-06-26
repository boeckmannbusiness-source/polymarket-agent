from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal
from pydantic import BaseModel, Field
from app.domain.assets.asset_id import AssetId

class MarketQualityDecision(str, Enum):
    APPROVED = "APPROVED"
    WATCH = "WATCH"
    BLOCKED = "BLOCKED"

class AssetSnapshot(BaseModel):
    asset_id: AssetId
    symbol: str
    venue: str
    market_cap: Decimal
    liquidity: Decimal
    holder_distribution: Dict[str, Decimal] = Field(default_factory=dict)
    asset_age_days: int
    route_snapshot: Dict[str, Any] = Field(default_factory=dict)
    evaluation_slot: int

class AdmissionDecision(str, Enum):
    ALLOW_SIMULATION = "ALLOW_SIMULATION"
    WATCH = "WATCH"
    BLOCK = "BLOCK"

class AdmissionReceipt(BaseModel):
    admission_id: str
    decision: AdmissionDecision
    decision_hash: str
    asset_snapshot_hash: str
    policy_version: str
    reasons: List[str] = Field(default_factory=list)
    created_slot: int
    valid_until_slot: int
