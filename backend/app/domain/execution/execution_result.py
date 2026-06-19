from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class FillInfo(BaseModel):
    fill_id: str
    size: Decimal
    price: Decimal
    fee: Decimal | None = None
    timestamp: datetime | None = None


class ExecutionResult(BaseModel):
    execution_id: str
    adapter: str
    status: str
    submitted_at: datetime | None = None
    completed_at: datetime | None = None
    fills: list[FillInfo] | None = None
    average_price: Decimal | None = None
    quantity_executed: Decimal | None = None
    fees: Decimal | None = None
    latency_ms: float | None = None
    simulated: bool = False
    fill_model: str | None = None
    execution_path: list[str] | None = None
    simulated_slippage: float | None = None
    simulated_latency_ms: float | None = None
    instruction_trace: list[str] | None = None
    metadata: dict | None = None
