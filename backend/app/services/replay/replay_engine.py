from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.execution import ExecutionResult, FillInfo
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.replay.replay_seed import ReplaySeed
from app.services.replay.execution_fingerprint import ExecutionFingerprint


class ReplayEngine:
    @staticmethod
    def replay(trace: ExecutionTrace) -> ExecutionResult:
        fills = []
        for i in range(len(trace.fill_prices)):
            fills.append(FillInfo(
                fill_id=str(uuid4()),
                size=trace.fill_sizes[i],
                price=trace.fill_prices[i],
                fee=trace.fill_fees[i],
                timestamp=datetime.now(timezone.utc),
            ))

        return ExecutionResult(
            execution_id=str(uuid4()),
            adapter=trace.plan.quote.source if trace.plan.quote else "replay",
            status="filled",
            submitted_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            fills=fills,
            average_price=trace.average_price,
            quantity_executed=trace.quantity_executed,
            fees=trace.total_fees,
            latency_ms=trace.latency_ms,
            simulated=True,
            fill_model="slippage_linear",
            execution_path=trace.instruction_trace_snapshot,
            simulated_slippage=float(trace.plan.slippage_bps or 0) / 10000.0,
            simulated_latency_ms=trace.latency_ms,
            instruction_trace=trace.instruction_trace_snapshot,
            metadata={
                "replayed": True,
                "original_execution_id": trace.execution_id,
                "seed": trace.seed.seed,
            },
        )

    @staticmethod
    def create_trace(
        result: ExecutionResult,
        intent: object,
        plan: object,
        seed: ReplaySeed,
    ) -> ExecutionTrace:
        fill_prices = [f.price for f in (result.fills or [])]
        fill_sizes = [f.size for f in (result.fills or [])]
        fill_fees = [f.fee or Decimal("0") for f in (result.fills or [])]

        trace = ExecutionTrace(
            execution_id=result.execution_id,
            intent=intent,
            plan=plan,
            seed=seed,
            instruction_trace_snapshot=result.instruction_trace or [],
            fill_prices=fill_prices,
            fill_sizes=fill_sizes,
            fill_fees=fill_fees,
            total_fees=result.fees or Decimal("0"),
            average_price=result.average_price or Decimal("0"),
            quantity_executed=result.quantity_executed or Decimal("0"),
            latency_ms=result.latency_ms or 0.0,
        )

        trace.fingerprint = ExecutionFingerprint.generate(intent, plan, result, seed)
        return trace
