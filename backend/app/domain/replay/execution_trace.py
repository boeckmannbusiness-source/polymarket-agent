from decimal import Decimal
from pydantic import BaseModel

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.replay.replay_seed import ReplaySeed


class ExecutionTrace(BaseModel):
    execution_id: str
    intent: ExecutionIntent
    plan: TransactionPlan
    seed: ReplaySeed
    instruction_trace_snapshot: list[str]
    fill_prices: list[Decimal]
    fill_sizes: list[Decimal]
    fill_fees: list[Decimal]
    total_fees: Decimal
    average_price: Decimal
    quantity_executed: Decimal
    latency_ms: float
    fingerprint: str | None = None
