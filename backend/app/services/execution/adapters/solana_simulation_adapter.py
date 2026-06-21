import uuid
from decimal import Decimal
from datetime import datetime, timezone
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.solana.models import TransactionReceipt
from app.domain.execution import ExecutionResult, FillInfo
from app.services.execution.transaction_builder.solana_builder import SolanaTransactionBuilder


class SolanaSimulationAdapter:
    """Simulates Solana transaction execution for Sprint 2.0.

    NO BROADCAST. Simulation only.
    """

    def __init__(self, transaction_builder: SolanaTransactionBuilder | None = None):
        self._builder = transaction_builder or SolanaTransactionBuilder()

    async def simulate_execution(self, plan: TransactionPlan) -> TransactionReceipt:
        # 1. Build the transaction envelope
        envelope = await self._builder.build_envelope(plan)

        # 2. Simulate the execution result
        success = len(plan.instructions) > 0

        receipt = TransactionReceipt(
            transaction_hash=f"sim_{uuid.uuid4().hex[:16]}",
            success=success,
            estimated_fees=envelope.fee_estimate,
            compute_units=len(plan.instructions) * 50000,
            execution_trace=[instr.instruction_type for instr in plan.instructions],
            metadata={
                "envelope_fingerprint": envelope.fingerprint(),
                "simulated_at": datetime.now(timezone.utc).isoformat()
            }
        )

        return receipt

    async def execute_to_result(self, plan: TransactionPlan) -> ExecutionResult:
        """Converts a simulation into a standard ExecutionResult."""
        receipt = await self.simulate_execution(plan)

        fills = []
        if receipt.success and plan.quote:
            fills.append(FillInfo(
                fill_id=str(uuid.uuid4()),
                size=plan.quote.expected_amount_out,
                price=plan.quote.estimated_price,
                fee=Decimal(str(receipt.estimated_fees)) / Decimal("1000000000"),
                timestamp=datetime.now(timezone.utc)
            ))

        return ExecutionResult(
            execution_id=receipt.transaction_hash,
            adapter="solana_simulation",
            status="filled" if receipt.success else "failed",
            submitted_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            fills=fills,
            average_price=plan.quote.estimated_price if plan.quote else Decimal("0"),
            quantity_executed=plan.quote.expected_amount_out if (plan.quote and receipt.success) else Decimal("0"),
            fees=Decimal(str(receipt.estimated_fees)) / Decimal("1000000000"),
            latency_ms=100.0,
            simulated=True,
            metadata={
                "receipt": receipt.model_dump(),
                "plan_id": str(getattr(plan, "id", "none"))
            }
        )
