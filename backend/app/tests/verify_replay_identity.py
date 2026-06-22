import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from app.domain.execution import ExecutionIntent, Instrument, ExecutionResult
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.replay.replay_seed import ReplaySeed
from app.services.replay.replay_engine import ReplayEngine
from app.services.execution.simulation import ExecutionSimulator

async def verify_identity():
    print("--- Starting Replay Identity Verification ---")

    # 1. Setup mock data
    instrument = Instrument(venue="live_jupiter", symbol="SOL-USDC", asset_identifier="SOL", quote_asset="USDC")
    quote = Quote(
        instrument=instrument,
        source="jupiter_simulated",
        estimated_price=Decimal("100.0"),
        amount_in=Decimal("1.0"),
        expected_amount_out=Decimal("100.0"),
        slippage_bps=100,
        timestamp=datetime.now(timezone.utc)
    )
    route = Route(venue="jupiter", route_type="DIRECT", hops=["SOL", "USDC"])
    constraints = ExecutionConstraints(max_slippage_bps=100)
    plan = TransactionPlan(
        quote=quote,
        route=route,
        constraints=constraints,
        instructions=[TransactionInstruction(
            instruction_type="swap",
            source_asset="SOL",
            target_asset="USDC",
            amount=Decimal("1.0")
        )],
        estimated_fees=5000,
        slippage_bps=100,
        serialized_payload_b64="dGVzdF9wYXlsb2Fk" # "test_payload"
    )

    intent = ExecutionIntent(
        instrument=instrument,
        side="buy",
        quantity=Decimal("1.0"),
        order_type="market",
        transaction_plan=plan
    )

    seed = ReplaySeed(seed=12345, timestamp_bucket=datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat())

    # 2. Generate original result
    simulator = ExecutionSimulator()
    original_result = await simulator.simulate(plan, adapter_name="jupiter_simulated", seed=seed)

    # 3. Create trace
    trace = ReplayEngine.create_trace(original_result, intent, plan, seed)

    # 4. Replay
    replayed_result = ReplayEngine.replay(trace)

    # 5. Verify Identity
    print(f"Original Execution ID: {original_result.execution_id}")
    print(f"Replayed Execution ID: {replayed_result.execution_id}")

    # Check key fields
    assert original_result.average_price == replayed_result.average_price, "Average price mismatch"
    assert original_result.quantity_executed == replayed_result.quantity_executed, "Quantity executed mismatch"
    assert original_result.fees == replayed_result.fees, "Fees mismatch"
    assert original_result.instruction_trace == replayed_result.instruction_trace, "Instruction trace mismatch"

    # Replay identity requirement: same quote, plan, payload, receipt, execution_trace
    # Trace contains intent and plan.
    assert trace.plan.quote.estimated_price == plan.quote.estimated_price
    assert trace.plan.serialized_payload_b64 == plan.serialized_payload_b64

    print("PASSED: Quote, Plan, and Payload identity confirmed in trace.")

    # Check receipt/result fields
    assert original_result.status == replayed_result.status
    assert original_result.quantity_executed == replayed_result.quantity_executed

    print("PASSED: Replayed Result matches Original Result (excluding IDs).")

    print("--- Replay Identity Verification Successful ---")

if __name__ == "__main__":
    asyncio.run(verify_identity())
