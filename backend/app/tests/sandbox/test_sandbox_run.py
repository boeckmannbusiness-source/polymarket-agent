import pytest
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.solana.models import TransactionEnvelope, TransactionPayload
from app.services.execution.simulation.chain_simulation_service import ChainSimulationService
from app.services.rpc.interfaces import RpcReader, RpcWriter
from app.services.replay.replay_engine import ReplayEngine
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.execution import ExecutionResult

@pytest.mark.asyncio
async def test_sandbox_reality_run():
    # 1. Setup mocks for RPC
    mock_rpc_reader = AsyncMock(spec=RpcReader)
    mock_rpc_reader.get_latest_blockhash.return_value = "fake_blockhash"

    mock_rpc_writer = AsyncMock(spec=RpcWriter)
    mock_rpc_writer.simulate_transaction.return_value = {
        "err": None,
        "unitsConsumed": 1234,
        "logs": ["sim log 1"],
        "slot": 100
    }

    # 2. Create services
    sim_service = ChainSimulationService(mock_rpc_reader, mock_rpc_writer)

    # 3. Simulate Signal -> Quote -> Plan -> Payload -> Simulate -> Receipt
    instrument = Instrument(venue="jupiter", symbol="SOL", asset_identifier="SOL", quote_asset="USDC")
    intent = ExecutionIntent(instrument=instrument, side="buy", quantity=Decimal("1.0"), order_type="market")
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("100"),
        expected_amount_out=Decimal("1"),
        estimated_price=Decimal("100"),
        slippage_bps=50,
        source="jupiter"
    )
    route = Route(venue="jupiter", hops=["USDC", "SOL"])
    constraints = ExecutionConstraints(max_slippage_bps=50)
    plan = TransactionPlan(
        quote=quote,
        route=route,
        constraints=constraints,
        instructions=[],
        serialized_payload_b64="base64_tx"
    )

    envelope = TransactionEnvelope(
        instructions=[],
        payload=TransactionPayload(serialized_payload_b64=plan.serialized_payload_b64),
        slippage_bps=50,
        fee_estimate=5000
    )

    # Run simulation
    snapshot = await sim_service.simulate(envelope)

    # Assertions for Objective 7
    assert snapshot.receipt.success is True
    assert snapshot.receipt.blockhash == "fake_blockhash"
    assert snapshot.receipt.compute_units == 1234

    # 4. Verify Replay preservation
    seed = ReplaySeed(seed=12345, timestamp_bucket="2023-01-01T00:00:00")
    result = ExecutionResult(
        execution_id="exec_1",
        adapter="jupiter",
        status="filled",
        submitted_at=MagicMock(),
        completed_at=MagicMock(),
        fills=[],
        average_price=Decimal("100"),
        quantity_executed=Decimal("1"),
        fees=Decimal("0.005"),
        latency_ms=100.0,
        instruction_trace=["ix1"]
    )

    trace = ReplayEngine.create_trace(
        result=result,
        intent=intent,
        plan=plan,
        seed=seed,
        simulation=snapshot
    )

    assert trace.simulation is not None
    assert trace.simulation.receipt.compute_units == 1234

    # Replay
    replayed_result = ReplayEngine.replay(trace)
    assert replayed_result.metadata["simulation"]["receipt"]["compute_units"] == 1234
    assert replayed_result.metadata["seed"] == 12345

    # Verify no broadcast
    mock_rpc_writer.send_transaction.assert_not_called()

    print("Sandbox reality run successful.")
