from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional

class OutcomeReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision_id: UUID
    timestamp: datetime
    realized_ev: float
    win_loss: bool
    calibration_delta: float
    prediction_error: float
    resolution_price: float

class ReplayParityReport(BaseModel):
    decision_id: UUID
    parity_score: float
    mismatch_reason: Optional[str] = None
    deterministic: bool
    reproduced_confidence: float
    reproduced_ev: float
