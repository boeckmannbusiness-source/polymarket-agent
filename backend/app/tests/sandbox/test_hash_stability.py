import pytest
import hashlib
import json
from decimal import Decimal
from app.domain.solana.models import SimulationReceipt, SimulationSnapshot, TransactionEnvelope, TransactionPayload
from app.services.replay.replay_engine import ReplayEngine
from app.domain.replay.execution_trace import ExecutionTrace
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_account_hash_order_stable_async():
    from app.services.execution.simulation.chain_simulation_service import ChainSimulationService
    from unittest.mock import AsyncMock

    mock_rpc = AsyncMock()
    mock_rpc.get_latest_blockhash.return_value = "hash"

    service = ChainSimulationService(mock_rpc)

    accounts1 = ["account1", "account2"]
    accounts2 = ["account2", "account1"]

    env = TransactionEnvelope(instructions=[], payload=TransactionPayload(serialized_payload_b64="tx"), slippage_bps=100, fee_estimate=10)

    mock_rpc.simulate_transaction.return_value = {"err": None, "accounts": accounts1, "unitsConsumed": 10, "slot": 1}
    snap1 = await service.simulate(env)

    mock_rpc.simulate_transaction.return_value = {"err": None, "accounts": accounts2, "unitsConsumed": 10, "slot": 1}
    snap2 = await service.simulate(env)

    # simulation_id is random, so we clear it for comparison or just check account_state_hash
    assert snap1.receipt.account_state_hash == snap2.receipt.account_state_hash

@pytest.mark.asyncio
async def test_simulation_hash_replay():
    """Verify stored_hash == replay_hash."""
    receipt = SimulationReceipt(
        success=True, compute_units=100, estimated_fee=10, logs=[], slot=100, blockhash="bh"
    )
    tx_message = "cGF5bG9hZA=="
    receipt.simulation_hash = receipt.calculate_hash(tx_message)
    receipt.hash = receipt.simulation_hash

    # Replay logic should re-calculate and match
    instr = Instrument(venue="v", symbol="s", asset_identifier="a", quote_asset="q")
    trace = ExecutionTrace(
        execution_id="id",
        intent=ExecutionIntent(instrument=instr, side="buy", quantity=Decimal("1"), order_type="market"),
        plan=TransactionPlan(
            quote=Quote(instrument=instr, source="s", amount_in=Decimal("1"), expected_amount_out=Decimal("1"), estimated_price=Decimal("1"), slippage_bps=1, timestamp=datetime.now(timezone.utc)),
            route=Route(venue="v", hops=[]),
            constraints=ExecutionConstraints(max_slippage_bps=1),
            serialized_payload_b64="cGF5bG9hZA==" # "payload" in b64
        ),
        seed=ReplaySeed(seed=1, timestamp_bucket="2024-01-01T00:00:00"),
        instruction_trace_snapshot=[],
        fill_prices=[Decimal("1")],
        fill_sizes=[Decimal("1")],
        fill_fees=[Decimal("0")],
        total_fees=Decimal("0"),
        average_price=Decimal("1"),
        quantity_executed=Decimal("1"),
        latency_ms=1.0,
        simulation=SimulationSnapshot(receipt=receipt, timestamp=1.0, rpc_endpoint="rpc")
    )

    # ReplayEngine._replay_internal(trace) should not raise HashMismatch
    ReplayEngine.replay(trace)

def test_simulation_hash_mutation():
    """Verify changing any protected field invalidates hash."""
    receipt = SimulationReceipt(
        success=True, compute_units=100, estimated_fee=10, logs=[], slot=100, blockhash="bh"
    )
    tx_message = "payload"
    original_hash = receipt.calculate_hash(tx_message)

    # Mutate slot
    receipt.slot = 101
    assert receipt.calculate_hash(tx_message) != original_hash
    receipt.slot = 100

    # Mutate compute_units
    receipt.compute_units = 101
    assert receipt.calculate_hash(tx_message) != original_hash
    receipt.compute_units = 100

    # Mutate fee_snapshot
    receipt.fee_snapshot = {"fee": 1}
    assert receipt.calculate_hash(tx_message) != original_hash

def test_decimal_hash_stability():
    """Verify 1, 1.0, 1.0000 produce identical hashes."""
    def get_hash(val):
        receipt = SimulationReceipt(
            success=True, compute_units=100, estimated_fee=10, logs=[], slot=100, blockhash="bh"
        )
        receipt.fee_snapshot = {"val": val}
        return receipt.calculate_hash("tx")

    h1 = get_hash(Decimal("1"))
    h2 = get_hash(Decimal("1.0"))
    h3 = get_hash(Decimal("1.000000"))

    assert h1 == h2 == h3

    # Also verify it's different from a different value
    h4 = get_hash(Decimal("1.000001"))
    assert h1 != h4
