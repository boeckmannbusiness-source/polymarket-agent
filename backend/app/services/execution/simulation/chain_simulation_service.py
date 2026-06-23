import time
from typing import Optional
from app.domain.solana.models import TransactionEnvelope, SimulationReceipt, SimulationSnapshot
from app.services.rpc.interfaces import RpcWriter, RpcReader


class ChainSimulationService:
    """Service for simulating Solana transactions against real chain state."""

    def __init__(self, rpc_reader: RpcReader, rpc_writer: RpcWriter):
        self.rpc_reader = rpc_reader
        self.rpc_writer = rpc_writer

    async def simulate(self, envelope: TransactionEnvelope) -> SimulationSnapshot:
        """Simulates the transaction and returns a snapshot."""

        # 1. Get latest blockhash for the simulation context
        blockhash = await self.rpc_reader.get_latest_blockhash()

        # 2. Perform simulation via RPC writer (which supports simulation even in sandbox)
        # Note: In real Solana, simulation usually requires the message to be built.
        # We assume the payload contains the base64 encoded transaction message/transaction.
        raw_sim_result = await self.rpc_writer.simulate_transaction(envelope.payload.serialized_payload_b64)

        # 3. Map raw result to SimulationReceipt
        # This is a simplified mapping, real Solana RPC response is more complex
        err = raw_sim_result.get("err")
        success = err is None

        # Extract units, logs etc from RPC response
        units_consumed = raw_sim_result.get("unitsConsumed", 0)
        logs = raw_sim_result.get("logs", [])

        # In a real scenario, we'd also get the slot from the RPC response header or meta
        # Here we use placeholders if not available
        slot = raw_sim_result.get("slot", 0)

        receipt = SimulationReceipt(
            success=success,
            compute_units=units_consumed,
            estimated_fee=envelope.fee_estimate, # Or calculated from units if possible
            logs=logs,
            slot=slot,
            blockhash=blockhash
        )

        snapshot = SimulationSnapshot(
            receipt=receipt,
            timestamp=time.time(),
            rpc_endpoint="solana-mainnet" # Should be dynamic in real impl
        )

        return snapshot
