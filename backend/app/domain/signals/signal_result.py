from datetime import datetime

from pydantic import BaseModel

from app.domain.signals.signal import Signal


class SignalResult(BaseModel):
    signal: Signal
    strategy_name: str
    generated_at: datetime
    diagnostics: dict | None = None
