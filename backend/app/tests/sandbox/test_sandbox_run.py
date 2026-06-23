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
from app.domain.solana.models import (
    TransactionEnvelope, TransactionPayload, SimulationInvalidationError,
    SimulationInvalidationReason, SimulationReceipt
)
from app.services.execution.simulation.chain_simulation_service import ChainSimulationService
from app.services.execution.simulation.validator import SimulationValidator
from app.services.rpc.interfaces import RpcReader
from app.services.rpc.solana_rpc_reader import SolanaRpcReader
from app.services.replay.replay_engine import ReplayEngine
from app.services.replay.offline_guard import ReplayIsolationViolation
from app.domain.replay.replay_seed import ReplaySeed
from app.domain.execution import ExecutionResult

# Redefine RpcReader mock to avoid AttributeError if it doesn't see simulate_transaction
class MockRpcReader(RpcReader):
    async def get_balance(self, address: str) -> int: return 0
    async def get_latest_blockhash(self) -> str: return "fake"
    async def get_token_accounts(self, owner: str) -> list: return []
    async def get_account_info(self, address: str) -> dict: return {}
    async def simulate_transaction(self, tx: str) -> dict: return {}

@pytest.mark.asyncio
async def test_sandbox_reality_run():
    # 1. Setup mocks for RPC
    mock_rpc_reader = AsyncMock(spec=MockRpcReader)
    mock_rpc_reader.get_latest_blockhash.return_value = "fake_blockhash"

    mock_rpc_reader.simulate_transaction.return_value = {
        "err": None,
        "unitsConsumed": 1234,
        "logs": ["sim log 1"],
        "slot": 100
    }

    # 2. Create services
    sim_service = ChainSimulationService(mock_rpc_reader)

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
    assert snapshot.receipt.hash is not None

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

@pytest.mark.asyncio
async def test_simulation_hardening_integrity():
    # Test Hash Mismatch
    instrument = Instrument(venue="jupiter", symbol="SOL", asset_identifier="SOL", quote_asset="USDC")
    intent = ExecutionIntent(instrument=instrument, side="buy", quantity=Decimal("1.0"), order_type="market")
    quote = Quote(instrument=instrument, amount_in=Decimal("100"), expected_amount_out=Decimal("1"), estimated_price=Decimal("100"), slippage_bps=50, source="jupiter")
    route = Route(venue="jupiter", hops=["USDC", "SOL"])
    constraints = ExecutionConstraints(max_slippage_bps=50)
    plan = TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=[], serialized_payload_b64="base64_tx")

    mock_rpc_reader = AsyncMock(spec=MockRpcReader)
    mock_rpc_reader.get_latest_blockhash.return_value = "fake_blockhash"
    mock_rpc_reader.simulate_transaction.return_value = {"err": None, "unitsConsumed": 1234, "logs": [], "slot": 100}

    sim_service = ChainSimulationService(mock_rpc_reader)
    snapshot = await sim_service.simulate(TransactionEnvelope(instructions=[], payload=TransactionPayload(serialized_payload_b64="base64_tx"), slippage_bps=50, fee_estimate=5000))

    # Tamper with hash
    snapshot.receipt.hash = "tampered_hash"

    seed = ReplaySeed(seed=12345, timestamp_bucket="2023-01-01T00:00:00")
    result = ExecutionResult(execution_id="exec_1", adapter="jupiter", status="filled", submitted_at=MagicMock(), completed_at=MagicMock(), fills=[], average_price=Decimal("100"), quantity_executed=Decimal("1"), fees=Decimal("0.005"), latency_ms=100.0)

    trace = ReplayEngine.create_trace(result=result, intent=intent, plan=plan, seed=seed, simulation=snapshot)

    with pytest.raises(SimulationInvalidationError) as excinfo:
        ReplayEngine.replay(trace)
    assert excinfo.value.reason == SimulationInvalidationReason.HASH_MISMATCH

@pytest.mark.asyncio
async def test_simulation_ttl_and_drift():
    # Test TTL Expired
    mock_rpc_reader = AsyncMock(spec=MockRpcReader)
    mock_rpc_reader.get_latest_blockhash.return_value = "fake_blockhash"
    mock_rpc_reader.simulate_transaction.return_value = {"err": None, "unitsConsumed": 1234, "logs": [], "slot": 100}

    sim_service = ChainSimulationService(mock_rpc_reader)
    snapshot = await sim_service.simulate(TransactionEnvelope(instructions=[], payload=TransactionPayload(serialized_payload_b64="base64_tx"), slippage_bps=50, fee_estimate=5000))

    # current_slot 300, expires at 100+150=250
    with pytest.raises(SimulationInvalidationError) as excinfo:
        SimulationValidator.validate(snapshot.receipt, current_slot=300)
    assert excinfo.value.reason == SimulationInvalidationReason.TTL_EXPIRED

    # Test Slot Drift
    # current_slot 120, simulated at 100, delta 20 > 10
    with pytest.raises(SimulationInvalidationError) as excinfo:
        SimulationValidator.validate(snapshot.receipt, current_slot=120, drift_threshold=10)
    assert excinfo.value.reason == SimulationInvalidationReason.SLOT_DRIFT

@pytest.mark.asyncio
async def test_replay_offline_isolation_mocked():
    # Corrected sync version since ReplayEngine.replay is sync
    seed = ReplaySeed(seed=12345, timestamp_bucket="2023-01-01T00:00:00")
    instrument = Instrument(venue="jupiter", symbol="SOL", asset_identifier="SOL", quote_asset="USDC")
    intent = ExecutionIntent(instrument=instrument, side="buy", quantity=Decimal("1.0"), order_type="market")
    quote = Quote(instrument=instrument, amount_in=Decimal("100"), expected_amount_out=Decimal("1"), estimated_price=Decimal("100"), slippage_bps=50, source="jupiter")
    route = Route(venue="jupiter", hops=["USDC", "SOL"])
    constraints = ExecutionConstraints(max_slippage_bps=50)
    plan = TransactionPlan(quote=quote, route=route, constraints=constraints, instructions=[], serialized_payload_b64="base_tx")
    result = ExecutionResult(execution_id="exec_1", adapter="jupiter", status="filled", submitted_at=MagicMock(), completed_at=MagicMock(), fills=[], average_price=Decimal("100"), quantity_executed=Decimal("1"), fees=Decimal("0.005"), latency_ms=100.0)

    trace = ReplayEngine.create_trace(result=result, intent=intent, plan=plan, seed=seed)

    # We need to simulate an async call being triggered or just check the guard manually
    from app.services.replay.offline_guard import ReplayOfflineGuard

    def check_guard_and_replay(t):
        if ReplayOfflineGuard.is_replay_active():
            # This is what _post would do
            raise ReplayIsolationViolation("Mocked violation")
        return result

    original_internal = ReplayEngine._replay_internal
    ReplayEngine._replay_internal = check_guard_and_replay

    try:
        with pytest.raises(ReplayIsolationViolation):
            ReplayEngine.replay(trace)
    finally:
        ReplayEngine._replay_internal = original_internal
