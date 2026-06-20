import time
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution import ExecutionResult, FillInfo
from app.services.execution.simulation.fill_simulator import FillSimulator
from app.domain.replay.replay_seed import ReplaySeed

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
        seed: ReplaySeed | None = None,
    ) -> ExecutionResult:
        start = time.time()

        if seed:
            import hashlib
            import uuid
            h = hashlib.sha256(f"{seed.seed}_exec".encode()).hexdigest()
            execution_id = str(uuid.UUID(h[:32]))
            submitted_at = datetime.fromisoformat(seed.timestamp_bucket)
        else:
            execution_id = str(uuid4())
            submitted_at = datetime.now(timezone.utc)

        fills = self._fill_simulator.simulate_fills(plan, seed=seed)
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

        if seed:
            completed_at = submitted_at
            latency_ms = simulated_latency
        else:
            completed_at = datetime.now(timezone.utc)
            latency_ms = max(elapsed, simulated_latency)

        return ExecutionResult(
            execution_id=execution_id,
            adapter=adapter_name,
            status="filled",
            submitted_at=submitted_at,
            completed_at=completed_at,
            fills=fills,
            average_price=avg_price,
            quantity_executed=total_executed,
            fees=total_fees,
            latency_ms=latency_ms,
            simulated=True,
            fill_model="slippage_linear",
            execution_path=execution_path,
            simulated_slippage=float(plan.slippage_bps or 0) / 10000.0,
            simulated_latency_ms=simulated_latency,
            instruction_trace=execution_path,
            metadata={
                "instruction_count": len(plan.instructions),
                "route_type": plan.route.route_type if plan.route else "unknown",
                "simulated": True,
            },
        )



