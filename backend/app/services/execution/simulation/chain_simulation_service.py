import time
import uuid
import hashlib
import json
from decimal import Decimal
from typing import Optional
from app.domain.solana.models import TransactionEnvelope, SimulationReceipt, SimulationSnapshot, SimulationInvalidationReason
from app.services.rpc.interfaces import RpcReader
from app.services.execution.simulation.fee_estimator import FeeEstimator
from app.services.execution.simulation.route_validator import RouteValidator
from app.services.execution.simulation.slippage_analyzer import SlippageAnalyzer


class ChainSimulationService:
    """Service for simulating Solana transactions against real chain state."""

    def __init__(self, rpc_reader: RpcReader):
        self.rpc_reader = rpc_reader
        self.route_validator = RouteValidator(rpc_reader)

    async def simulate(self, envelope: TransactionEnvelope) -> SimulationSnapshot:
        """Simulates the transaction and returns a snapshot."""

        # 1. Route Validation (Reality Check)
        route_status = await self.route_validator.validate_route(envelope)

        # 2. Get latest blockhash for the simulation context
        blockhash = await self.rpc_reader.get_latest_blockhash()

        # 3. Perform simulation via RPC reader (read-only)
        # Note: In real Solana, simulation usually requires the message to be built.
        # We assume the payload contains the base64 encoded transaction message/transaction.
        raw_sim_result = await self.rpc_reader.simulate_transaction(envelope.payload.serialized_payload_b64)

        # 4. Map raw result to SimulationReceipt
        err = raw_sim_result.get("err")
        success = err is None and route_status == "VALID"

        # Extract units, logs etc from RPC response
        units_consumed = raw_sim_result.get("unitsConsumed", 0)
        logs = raw_sim_result.get("logs", [])

        # In a real scenario, we'd also get the slot from the RPC response header or meta
        slot = raw_sim_result.get("slot", 0)

        # 5. Compute Unit Reality
        # If the planner expected much fewer units than consumed, it might be an unrealistic plan
        expected_units = envelope.metadata.get("expected_compute_units", units_consumed)
        compute_delta = units_consumed - expected_units

        # 6. Fee Reality Layer
        priority_fee_lamports = envelope.metadata.get("priority_fee_lamports", 0)
        total_fee, fee_confidence = FeeEstimator.estimate_fee(units_consumed, priority_fee_lamports)

        # 7. Slippage Behavior Modeling
        # Assuming we can extract output amount from logs or simulation result
        # For this MVP, we simulate extracted amount
        simulated_out = envelope.metadata.get("simulated_out_amount", Decimal("0"))
        expected_out = envelope.metadata.get("expected_out_amount", Decimal("0"))

        effective_slippage, slippage_status = SlippageAnalyzer.analyze_slippage(
            expected_out,
            simulated_out,
            fee=Decimal(str(total_fee)),
            slippage_bps_threshold=envelope.slippage_bps
        )

        receipt = SimulationReceipt(
            success=success,
            compute_units=units_consumed,
            estimated_fee=total_fee,
            logs=logs,
            slot=slot,
            blockhash=blockhash,
            created_slot=slot,

            # Reality Expansion
            simulation_id=str(uuid.uuid4()),
            account_state_hash=hashlib.sha256(json.dumps(sorted(raw_sim_result.get("accounts", []), key=lambda x: str(x)), sort_keys=True).encode()).hexdigest(),
            route_metadata={"status": route_status},
            valid_until_slot=slot + 150,
            compute_delta=compute_delta,
            fee_snapshot={"total_fee": total_fee, "confidence": fee_confidence},
            route_snapshot={"instructions": len(envelope.instructions)},
            slippage_snapshot={"effective_slippage_bps": effective_slippage, "status": slippage_status},
            wallet_context=envelope.metadata.get("wallet_context", {})
        )

        # Validate Compute Delta (e.g. 10% threshold)
        if expected_units > 0 and (compute_delta / expected_units) > 0.1:
             receipt.metadata["invalidation_reason"] = "COMPUTE_UNIT_DELTA_EXCEEDED"
             # We don't mark success=False here necessarily, but we flag it

        receipt.expires_at_slot = receipt.valid_until_slot
        receipt.simulation_hash = receipt.calculate_hash(envelope.payload.serialized_payload_b64)
        receipt.hash = receipt.simulation_hash

        snapshot = SimulationSnapshot(
            receipt=receipt,
            timestamp=time.time(),
            rpc_endpoint="solana-mainnet"
        )

        return snapshot
