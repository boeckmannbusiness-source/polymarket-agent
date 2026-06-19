from pydantic import BaseModel


class ExecutionConstraints(BaseModel):
    max_slippage_bps: int
    max_latency_ms: int | None = None
    max_price_impact: float | None = None
    require_atomic_execution: bool = True
