import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution import ExecutionResult, FillInfo
from app.services.execution.simulation.fill_simulator import FillSimulator

BASE_LATENCY_MS = 150.0
LATENCY_PER_INSTRUCTION_MS = 50.0


class ExecutionSimulator:
    """Orchestrates a deterministic execution simulation from a TransactionPlan.

    Produces a fully populated ExecutionResult with simulated fills, latency, and fees.
    """

    def __init__(self, fill_simulator: FillSimulator | None = None):
        self._fill_simulator = fill_simulator or FillSimulator()

    async def simulate(
        self,
        plan: TransactionPlan,
        adapter_name: str = "jupiter_simulated",
    ) -> ExecutionResult:
        start = time.time()
        submitted_at = datetime.now(timezone.utc)

        fills = self._fill_simulator.simulate_fills(plan)
        total_executed = sum(f.size for f in fills) if fills else Decimal("0")

        total_fees = Decimal(str(plan.estimated_fees or 0)) / Decimal("1000000")
        for fill in fills:
            if fill.fee is not None:
                total_fees += fill.fee

        avg_price = FillSimulator.compute_average_price(fills) if fills else Decimal("0")

        simulated_latency = len(plan.instructions) * LATENCY_PER_INSTRUCTION_MS + BASE_LATENCY_MS

        execution_path = [instr.instruction_type for instr in plan.instructions]
        if plan.route and plan.route.hops:
            execution_path = plan.route.hops

        elapsed = (time.time() - start) * 1000

        return ExecutionResult(
            execution_id=str(uuid4()),
            adapter=adapter_name,
            status="filled",
            submitted_at=submitted_at,
            completed_at=datetime.now(timezone.utc),
            fills=fills,
            average_price=avg_price,
            quantity_executed=total_executed,
            fees=total_fees,
            latency_ms=max(elapsed, simulated_latency),
            simulated=True,
            fill_model="slippage_linear",
            execution_path=execution_path,
            simulated_slippage=float(plan.slippage_bps or 0) / 10000.0,
            simulated_latency_ms=simulated_latency,
            metadata={
                "instruction_count": len(plan.instructions),
                "route_type": plan.route.route_type if plan.route else "unknown",
                "simulated": True,
            },
        )



