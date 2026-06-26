import hashlib
import json
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class CapitalDecision(str, Enum):
    ALLOW = "ALLOW"
    LIMIT = "LIMIT"
    BLOCK = "BLOCK"


class ExposureState(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    REJECT = "REJECT"


class CapitalPolicy(BaseModel):
    policy_version: str
    max_position_size: Decimal
    max_daily_loss: Decimal
    max_total_exposure: Decimal
    max_asset_exposure: Decimal
    emergency_stop: bool = False


class ExposureReport(BaseModel):
    position_ratio: Decimal
    risk_score: Decimal
    exposure_state: ExposureState


class RiskReceipt(BaseModel):
    risk_id: str
    capital_decision: CapitalDecision
    policy_version: str
    risk_snapshot: Dict[str, Any]
    reason_codes: List[str]
    created_slot: int
    valid_until_slot: int
    risk_hash: str

    def calculate_hash(self) -> str:
        """
        Calculates a deterministic fingerprint of the risk decision.
        Hash inputs: policy_version, capital_decision, risk_snapshot, reason_codes
        """
        def canonical_serialize(obj):
            if isinstance(obj, Decimal):
                normalized = obj.normalize()
                return f"{normalized:f}"
            if isinstance(obj, dict):
                return {k: canonical_serialize(v) for k, v in sorted(obj.items())}
            if isinstance(obj, list):
                return [canonical_serialize(i) for i in obj]
            return obj

        components = {
            "policy_version": self.policy_version,
            "capital_decision": self.capital_decision,
            "risk_snapshot": canonical_serialize(self.risk_snapshot),
            "reason_codes": sorted(self.reason_codes)
        }

        raw = json.dumps(components, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def verify(self) -> bool:
        return self.risk_hash == self.calculate_hash()
