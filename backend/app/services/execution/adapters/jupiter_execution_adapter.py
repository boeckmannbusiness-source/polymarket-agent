from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from app.exchanges.adapters.base_execution_adapter import BaseExecutionAdapter
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution import ExecutionResult, FillInfo
from app.services.execution.adapters.jupiter_instruction_simulator import JupiterInstructionSimulator
from app.services.execution.simulation.execution_math import compute_average_price, compute_estimated_latency_ms


class JupiterExecutionAdapter(BaseExecutionAdapter):
    def __init__(self, instruction_simulator: JupiterInstructionSimulator | None = None):
        self._simulator = instruction_simulator or JupiterInstructionSimulator()

    async def execute(self, plan: TransactionPlan) -> ExecutionResult:
        submitted_at = datetime.now(timezone.utc)

        fill_events = self._simulator.simulate_instructions(plan)

        fills: list[FillInfo] = [
            FillInfo(
                fill_id=str(uuid4()),
                size=fe.amount_out,
                price=fe.price,
                fee=fe.fee,
                timestamp=fe.timestamp,
            )
            for fe in fill_events
        ]

        total_executed = sum(f.size for f in fills) if fills else Decimal("0")
        total_fees = sum(f.fee for f in fills) if fills else Decimal("0")
        if plan.estimated_fees:
            total_fees += Decimal(str(plan.estimated_fees)) / Decimal("1000000")

        avg_price = compute_average_price(fills) if fills else Decimal("0")
        total_latency = compute_estimated_latency_ms(plan.instructions)
        instruction_trace = [fe.instruction_type for fe in fill_events]

        return ExecutionResult(
            execution_id=str(uuid4()),
            adapter="jupiter_simulated",
            status="filled",
            submitted_at=submitted_at,
            completed_at=datetime.now(timezone.utc),
            fills=fills,
            average_price=avg_price,
            quantity_executed=total_executed,
            fees=total_fees,
            latency_ms=total_latency,
            simulated=True,
            fill_model="slippage_linear",
            execution_path=instruction_trace,
            simulated_slippage=float(plan.slippage_bps or 0) / 10000.0,
            simulated_latency_ms=total_latency,
            instruction_trace=instruction_trace,
            metadata={
                "instruction_count": len(plan.instructions),
                "route_type": plan.route.route_type if plan.route else "unknown",
                "simulated": True,
            },
        )

    async def health_check(self) -> dict:
        return {"status": "ok", "adapter": "jupiter_simulated"}

    async def get_supported_assets(self) -> list[str]:
        return ["SOL", "USDC"]
