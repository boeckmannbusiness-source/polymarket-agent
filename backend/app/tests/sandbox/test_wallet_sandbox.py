import pytest
import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from app.domain.wallet.models import WalletCapabilityState, WalletReceipt
from app.services.wallet.ephemeral_provider import EphemeralWalletProvider
from app.services.wallet.session.manager import WalletSessionManager
from app.services.wallet.signing_sandbox import SigningSandbox
from app.services.execution.governance.execution_governor import ExecutionGovernor
from app.domain.execution_authorization.models import ExecutionMode


@pytest.fixture
def governor():
    return ExecutionGovernor(mode=ExecutionMode.SANDBOX)


@pytest.fixture
def provider():
    return EphemeralWalletProvider()


@pytest.fixture
def session_manager(provider):
    return WalletSessionManager(provider=provider, max_session_minutes=30)


@pytest.fixture
def sandbox(session_manager, provider, governor):
    return SigningSandbox(session_manager, provider, governor)


@pytest.mark.asyncio
async def test_wallet_destroy(session_manager, provider):
    session = await session_manager.create_session(
        capabilities=[WalletCapabilityState.SIGN_ONLY]
    )
    address = session.wallet.address

    # Verify key exists in provider
    assert address in provider._keys

    # Destroy session
    session_manager.destroy_session(session.session_id)

    # Verify key is removed from provider
    assert address not in provider._keys
    # Verify session is no longer retrievable
    assert session_manager.get_session(session.session_id) is None


@pytest.mark.asyncio
async def test_wallet_expiration(provider):
    # Create manager with 0 TTL for immediate expiration
    short_manager = WalletSessionManager(provider=provider, max_session_minutes=0)

    session = await short_manager.create_session()
    session.expires_at = time.time() - 1

    assert session.is_expired()
    assert short_manager.get_session(session.session_id) is None
    # Key should be destroyed
    assert session.wallet.address not in provider._keys


@pytest.mark.asyncio
async def test_wallet_no_persistence(provider):
    address = await provider.generate_keypair()

    with pytest.raises(PermissionError, match="Persistence is forbidden"):
        provider.save()

    with pytest.raises(PermissionError, match="Exporting private keys is forbidden"):
        provider.export_private_key(address)


@pytest.mark.asyncio
async def test_sign_without_session(sandbox):
    with pytest.raises(PermissionError, match="Session is invalid"):
        await sandbox.sign_transaction("invalid_session", "payload")


@pytest.mark.asyncio
async def test_sign_with_expired_session(session_manager, sandbox):
    session = await session_manager.create_session(
        capabilities=[WalletCapabilityState.SIGN_ONLY]
    )
    session.expires_at = time.time() - 1

    with pytest.raises(PermissionError, match="Session is invalid"):
        await sandbox.sign_transaction(session.session_id, "payload")


@pytest.mark.asyncio
async def test_sandbox_forbidden_operations(sandbox):
    with pytest.raises(PermissionError, match="send_transaction is forbidden"):
        sandbox.send_transaction()

    with pytest.raises(PermissionError, match="broadcast is forbidden"):
        sandbox.broadcast()


@pytest.mark.asyncio
async def test_replay_wallet_isolation():
    from app.domain.replay.execution_trace import ExecutionTrace
    from app.services.replay.replay_engine import ReplayEngine
    from app.domain.execution.execution_intent import ExecutionIntent
    from app.domain.planning.transaction_plan import TransactionPlan
    from app.domain.replay.replay_seed import ReplaySeed
    from app.domain.execution.instrument import Instrument
    from app.domain.planning.quote import Quote
    from app.domain.planning.route import Route
    from app.domain.planning.execution_constraints import ExecutionConstraints

    # Mock a trace with a wallet receipt
    receipt = WalletReceipt(
        wallet_session_id="session_123",
        capability_state=WalletCapabilityState.SIGN_ONLY,
        signature_metadata={"algo": "hmac-sha256"}
    )

    instr = Instrument(
        venue="jupiter",
        symbol="SOL/USDC",
        asset_identifier="SOL",
        quote_asset="USDC"
    )

    # Minimal trace for replay
    trace = ExecutionTrace(
        execution_id="exec_123",
        intent=ExecutionIntent(
            instrument=instr,
            side="buy",
            quantity=Decimal("1"),
            order_type="market"
        ),
        plan=TransactionPlan(
            serialized_payload_b64="cGF5bG9hZA==",
            quote=Quote(
                instrument=instr,
                source="jupiter",
                amount_in=Decimal("100"),
                expected_amount_out=Decimal("1"),
                estimated_price=Decimal("100"),
                slippage_bps=100,
                timestamp=datetime.now(timezone.utc)
            ),
            route=Route(
                venue="jupiter",
                hops=[]
            ),
            constraints=ExecutionConstraints(
                max_slippage_bps=100
            ),
            instructions=[]
        ),
        seed=ReplaySeed(seed=12345, timestamp_bucket="2024-01-01T00:00:00"),
        instruction_trace_snapshot=[],
        fill_prices=[Decimal("100")],
        fill_sizes=[Decimal("1")],
        fill_fees=[Decimal("0")],
        total_fees=Decimal("0"),
        average_price=Decimal("100"),
        quantity_executed=Decimal("1"),
        latency_ms=10.0,
        wallet_receipt=receipt
    )

    result = ReplayEngine.replay(trace)
    assert result.metadata["wallet_receipt"]["wallet_session_id"] == "session_123"
    assert "replayed" in result.metadata
