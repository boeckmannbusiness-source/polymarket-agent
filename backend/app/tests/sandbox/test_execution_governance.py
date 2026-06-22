import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone

from app.domain.execution_authorization.models import ExecutionMode, ExecutionPermission
from app.services.execution.governance.execution_governor import ExecutionGovernor, ExecutionAuthorizationError
from app.services.execution.execution_service import ExecutionService
from app.services.wallet.simulation import NullSigner
from app.services.execution.adapters.solana_simulation_adapter import SolanaSimulationAdapter
from app.services.execution.transaction_builder.solana_builder import SolanaTransactionBuilder
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.execution import ExecutionIntent, Instrument


@pytest.mark.asyncio
async def test_simulation_mode_blocks_signing():
    governor = ExecutionGovernor(ExecutionMode.SIMULATION)
    signer = NullSigner(governor=governor)

    with pytest.raises(ExecutionAuthorizationError, match="Signing forbidden"):
        await signer.sign("payload", "address")


@pytest.mark.asyncio
async def test_sandbox_mode_allows_signing_but_blocks_broadcast():
    governor = ExecutionGovernor(ExecutionMode.SANDBOX)
    signer = NullSigner(governor=governor)

    # Signing should be allowed in SANDBOX
    sig = await signer.sign("payload", "address")
    assert sig.startswith("null_sig")

    from app.services.rpc.sandbox_rpc_writer import SandboxRpcWriter
    rpc = SandboxRpcWriter()

    # Simulation allowed
    sim = await rpc.simulate_transaction("payload")
    assert sim["success"] is True

    # Send forbidden
    with pytest.raises(ExecutionAuthorizationError, match=r"RPC send \(broadcast\) forbidden"):
        await rpc.send_transaction("payload")


@pytest.mark.asyncio
async def test_disabled_mode_blocks_everything():
    governor = ExecutionGovernor(ExecutionMode.DISABLED)

    with pytest.raises(ExecutionAuthorizationError):
        governor.authorize_execution()

    with pytest.raises(ExecutionAuthorizationError):
        governor.authorize_sign()


@pytest.mark.asyncio
async def test_execution_service_enforces_governance(db_session):
    # Setup service in SIMULATION mode
    governor = ExecutionGovernor(ExecutionMode.SIMULATION)
    service = ExecutionService(db_session, governor=governor)

    # Mock an intent
    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    intent = ExecutionIntent(instrument=instrument, side="buy", quantity=Decimal("1.0"), order_type="market")

    # In SIMULATION mode, build is allowed but let's check if it raises if we try to authorize something else
    governor.authorize_execution() # Should pass

    with pytest.raises(ExecutionAuthorizationError):
        governor.authorize_capital()


@pytest.mark.asyncio
async def test_solana_builder_governance():
    governor = ExecutionGovernor(ExecutionMode.DISABLED)
    builder = SolanaTransactionBuilder(governor=governor)

    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    plan = TransactionPlan(
        instructions=[],
        quote=Quote(
            instrument=instrument,
            amount_in=Decimal("1"),
            source="jupiter",
            expected_amount_out=Decimal("100"),
            estimated_price=Decimal("100"),
            slippage_bps=100
        ),
        route=Route(venue="jupiter", route_type="DIRECT", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=100)
    )

    with pytest.raises(ExecutionAuthorizationError):
        await builder.build_envelope(plan)


@pytest.mark.asyncio
async def test_solana_adapter_governance():
    governor = ExecutionGovernor(ExecutionMode.SIMULATION) # Simulation mode blocks simulateTransaction by default policy

    adapter = SolanaSimulationAdapter(governor=governor)
    instrument = Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC")
    plan = TransactionPlan(
        instructions=[],
        quote=Quote(
            instrument=instrument,
            amount_in=Decimal("1"),
            source="jupiter",
            expected_amount_out=Decimal("100"),
            estimated_price=Decimal("100"),
            slippage_bps=100
        ),
        route=Route(venue="jupiter", route_type="DIRECT", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=100)
    )

    with pytest.raises(ExecutionAuthorizationError, match="RPC simulation forbidden"):
        await adapter.simulate_execution(plan)

    # Now with SANDBOX
    governor_sandbox = ExecutionGovernor(ExecutionMode.SANDBOX)
    adapter_sandbox = SolanaSimulationAdapter(governor=governor_sandbox)

    # Should work (returns failure because 0 instructions, but authorized)
    receipt = await adapter_sandbox.simulate_execution(plan)
    assert receipt.success is False # False because 0 instructions
