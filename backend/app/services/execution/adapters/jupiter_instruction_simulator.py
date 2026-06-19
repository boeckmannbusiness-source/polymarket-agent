from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.services.execution.simulation.fill_model import FillEvent
from app.services.execution.simulation.execution_math import (
    compute_slippage_price,
    compute_fee,
    compute_estimated_latency_ms,
)

BASE_LATENCY_MS = 100.0
LATENCY_PER_INSTRUCTION_MS = 50.0


class JupiterInstructionSimulator:
    def __init__(self, base_latency_ms: float = BASE_LATENCY_MS, per_instruction_latency_ms: float = LATENCY_PER_INSTRUCTION_MS):
        self._base_latency_ms = base_latency_ms
        self._per_instruction_latency_ms = per_instruction_latency_ms

    def simulate_instructions(self, plan: TransactionPlan) -> list[FillEvent]:
        fills: list[FillEvent] = []
        for i, instruction in enumerate(plan.instructions):
            fill = self._simulate_instruction(i, instruction, plan)
            fills.append(fill)
        return fills

    def _simulate_instruction(self, index: int, instruction: TransactionInstruction, plan: TransactionPlan) -> FillEvent:
        base_price = plan.quote.estimated_price or Decimal("0")
        slippage_bps = plan.slippage_bps or 0
        executed_price = compute_slippage_price(base_price, slippage_bps)
        fee = compute_fee(instruction.amount)
        fee_in_asset = fee
        amount_in = instruction.amount
        amount_out = amount_in - fee_in_asset if executed_price > Decimal("0") else Decimal("0")

        return FillEvent(
            instruction_index=index,
            instruction_type=instruction.instruction_type,
            source_asset=instruction.source_asset,
            target_asset=instruction.target_asset,
            amount_in=amount_in,
            amount_out=amount_out,
            price=executed_price,
            fee=fee_in_asset,
            slippage_bps=slippage_bps,
            latency_ms=self._base_latency_ms + (index + 1) * self._per_instruction_latency_ms,
            timestamp=datetime.now(timezone.utc),
        )
