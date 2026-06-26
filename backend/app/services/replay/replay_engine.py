from typing import Optional, Any
from app.domain.solana.models import SimulationSnapshot, SimulationInvalidationError, SimulationInvalidationReason
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution.execution_intent import ExecutionIntent
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.execution import ExecutionResult, FillInfo
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.replay.execution_snapshot import ExecutionAuthorizationSnapshot
from app.services.replay.execution_fingerprint import ExecutionFingerprint
from app.services.replay.offline_guard import ReplayOfflineGuard


class ReplayEngine:
    @staticmethod
    def replay(trace: ExecutionTrace) -> ExecutionResult:
        with ReplayOfflineGuard.enforce():
            return ReplayEngine._replay_internal(trace)

    @staticmethod
    def _replay_internal(trace: ExecutionTrace) -> ExecutionResult:
        if trace.simulation and trace.simulation.receipt:
            receipt = trace.simulation.receipt
            recomputed = receipt.calculate_hash(trace.plan.serialized_payload_b64)

            # Verify both legacy hash and new simulation_hash if present
            if receipt.hash and receipt.hash != recomputed:
                raise SimulationInvalidationError(
                    SimulationInvalidationReason.HASH_MISMATCH,
                    f"Simulation hash mismatch: {receipt.hash} != {recomputed}"
                )

            if receipt.simulation_hash and receipt.simulation_hash != recomputed:
                raise SimulationInvalidationError(
                    SimulationInvalidationReason.HASH_MISMATCH,
                    f"Simulation reality hash mismatch: {receipt.simulation_hash} != {recomputed}"
                )

        if trace.seed:
            import hashlib
            import uuid
            from datetime import datetime
            h_exec = hashlib.sha256(f"{trace.seed.seed}_exec".encode()).hexdigest()
            execution_id = str(uuid.UUID(h_exec[:32]))
            submitted_at = datetime.fromisoformat(trace.seed.timestamp_bucket)
            completed_at = submitted_at
        else:
            execution_id = trace.execution_id
            submitted_at = datetime.now(timezone.utc)
            completed_at = submitted_at

        fills = []
        for i in range(len(trace.fill_prices)):
            if trace.seed:
                import hashlib
                import uuid
                from datetime import datetime
                h_fill = hashlib.sha256(f"{trace.seed.seed}_{i}".encode()).hexdigest()
                fill_id = str(uuid.UUID(h_fill[:32]))
                fill_timestamp = datetime.fromisoformat(trace.seed.timestamp_bucket)
            else:
                fill_id = str(uuid4())
                fill_timestamp = datetime.now(timezone.utc)

            fills.append(FillInfo(
                fill_id=fill_id,
                size=trace.fill_sizes[i],
                price=trace.fill_prices[i],
                fee=trace.fill_fees[i],
                timestamp=fill_timestamp,
            ))

        metadata = {
            "replayed": True,
            "original_execution_id": trace.execution_id,
            "seed": trace.seed.seed,
        }
        if trace.simulation:
            metadata["simulation"] = trace.simulation.model_dump()

        if trace.wallet_receipt:
            metadata["wallet_receipt"] = trace.wallet_receipt.model_dump()

        if trace.admission:
            metadata["admission"] = trace.admission.model_dump()

        return ExecutionResult(
            execution_id=execution_id,
            adapter=trace.plan.quote.source if trace.plan.quote and trace.plan.quote.source and trace.plan.quote.source != "jupiter_simulated" else "jupiter_simulated",
            status="filled",
            submitted_at=submitted_at,
            completed_at=completed_at,
            fills=fills,
            average_price=trace.average_price,
            quantity_executed=trace.quantity_executed,
            fees=trace.total_fees,
            latency_ms=trace.latency_ms,
            simulated=True,
            fill_model="slippage_linear",
            execution_path=trace.instruction_trace_snapshot or [],
            simulated_slippage=float(trace.plan.slippage_bps or 0) / 10000.0,
            simulated_latency_ms=trace.latency_ms,
            instruction_trace=trace.instruction_trace_snapshot or [],
            metadata=metadata,
        )

    @staticmethod
    def create_trace(
        result: ExecutionResult,
        intent: ExecutionIntent,
        plan: TransactionPlan,
        seed: ReplaySeed,
        authorization: ExecutionAuthorizationSnapshot | None = None,
        simulation: SimulationSnapshot | None = None,
        capability: CapabilitySnapshot | None = None,
        wallet_receipt: Any | None = None, # WalletReceipt
        admission: Any | None = None, # AdmissionReceipt
    ) -> ExecutionTrace:
        fill_prices = [f.price for f in (result.fills or [])]
        fill_sizes = [f.size for f in (result.fills or [])]
        fill_fees = [f.fee or Decimal("0") for f in (result.fills or [])]

        # Use execution_path if instruction_trace is None (backward compatibility with simulator)
        trace_snapshot = result.instruction_trace
        if trace_snapshot is None and result.execution_path:
            trace_snapshot = result.execution_path

        trace = ExecutionTrace(
            execution_id=result.execution_id,
            intent=intent,
            plan=plan,
            seed=seed,
            instruction_trace_snapshot=trace_snapshot or [],
            fill_prices=fill_prices,
            fill_sizes=fill_sizes,
            fill_fees=fill_fees,
            total_fees=result.fees or Decimal("0"),
            average_price=result.average_price or Decimal("0"),
            quantity_executed=result.quantity_executed or Decimal("0"),
            latency_ms=result.latency_ms or 0.0,
            authorization=authorization,
            simulation=simulation,
            capability=capability,
            wallet_receipt=wallet_receipt,
            admission=admission,
        )

        trace.fingerprint = ExecutionFingerprint.generate(intent, plan, result, seed)
        return trace
