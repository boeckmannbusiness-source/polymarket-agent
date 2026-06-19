from decimal import Decimal

from pydantic import BaseModel

from app.domain.signals.signal_action import SignalAction
from app.domain.execution.instrument import Instrument


class Signal(BaseModel):
    instrument: Instrument
    action: SignalAction
    confidence: float
    quantity: Decimal | None = None
    metadata: dict | None = None
