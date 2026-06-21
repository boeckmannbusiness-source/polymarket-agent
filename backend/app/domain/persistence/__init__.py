from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional
from datetime import datetime


class VenueExecutionMetadata(BaseModel):
    """Venue-specific execution metadata, decoupled from core models."""
    model_config = ConfigDict(extra="allow")

    venue_id: str
    execution_provider: str
    raw_payload: Optional[dict[str, Any]] = None


class TradeContext(BaseModel):
    """Contextual information for a trade across different venues."""
    model_config = ConfigDict(extra="allow")

    strategy_id: Optional[str] = None
    signal_id: Optional[str] = None
    execution_metadata: Optional[VenueExecutionMetadata] = None
    compat_outcome: Optional[str] = None
    compat_condition_id: Optional[str] = None


class ExecutionContext(BaseModel):
    """Encapsulates the full context of an execution event."""
    model_config = ConfigDict(extra="allow")

    trace_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trade_context: Optional[TradeContext] = None
    venue_metadata: Optional[VenueExecutionMetadata] = None
