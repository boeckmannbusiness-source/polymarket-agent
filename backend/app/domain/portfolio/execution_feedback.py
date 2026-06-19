from pydantic import BaseModel


class ExecutionFeedback(BaseModel):
    execution_id: str
    signal_id: str | None = None
    result_status: str
    portfolio_delta: float  # net asset value change
    slippage_realized: float  # bps
    fee_realized: float  # in quote asset
    route_efficiency: float  # 0.0–1.0
    latency_ms: float
    metadata: dict | None = None
