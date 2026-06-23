from typing import Optional
from decimal import Decimal
from pydantic import BaseModel

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.solana.models import SimulationSnapshot
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.replay.execution_snapshot import ExecutionAuthorizationSnapshot


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
    simulation: Optional[SimulationSnapshot] = None
    capability: Optional[CapabilitySnapshot] = None
    authorization: Optional[ExecutionAuthorizationSnapshot] = None
    fingerprint: str | None = None
