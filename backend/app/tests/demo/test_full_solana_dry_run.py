import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.domain.signals import Signal, SignalAction
from app.domain.execution import Instrument, ExecutionIntent
from app.domain.assets import AssetId, AssetResolution, Asset, AssetMetadata
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_instruction import TransactionInstruction

from app.services.assets import AssetRegistry
from app.services.planning import Planner
from app.services.planning.jupiter.client import JupiterQuoteClient
from app.services.execution.transaction_builder.solana_builder import SolanaTransactionBuilder
from app.services.execution.adapters.solana_simulation_adapter import SolanaSimulationAdapter

@pytest.mark.asyncio
async def test_full_solana_dry_run():
    # 1. Setup
    instrument = Instrument(
        venue="jupiter",
        symbol="SOL/USDC",
        asset_identifier="So11111111111111111111111111111111111111112",
        quote_asset="EPjFW36v7qDETR7TV16P8V8ve7vMvu187iwd9GZfcKW"
    )

    signal = Signal(
        action=SignalAction.BUY,
        instrument=instrument,
        quantity=Decimal("1.0"),
        confidence=0.8,
        metadata={"strategy_id": "test_strat"}
    )

    # 2. Asset Resolution (Mocked for Demo)
    asset_res = AssetResolution(
        asset=Asset(
            asset_id=AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC"),
            decimals=9,
            metadata=AssetMetadata(external_identifiers={"mint": instrument.asset_identifier})
        ),
        source="registry",
        confidence=1.0
    )

    # 3. Planning & Quoting
    # We use a real Quote object but skip the actual API call for the demo to ensure stability
    quote = Quote(
        instrument=instrument,
        amount_in=Decimal("1.0"),
        expected_amount_out=Decimal("100.0"),
        estimated_price=Decimal("100.0"),
        slippage_bps=100,
        source="jupiter_mock",
        timestamp=datetime.now(timezone.utc)
    )

    plan = TransactionPlan(
        quote=quote,
        route=Route(venue="jupiter", route_type="DIRECT", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=100),
        instructions=[
            TransactionInstruction(
                instruction_type="SWAP",
                source_asset="SOL",
                target_asset="USDC",
                amount=Decimal("1.0")
            )
        ],
        estimated_fees=5000,
        slippage_bps=100
    )

    # 4. Transaction Construction
    builder = SolanaTransactionBuilder()
    envelope = await builder.build_envelope(plan)

    assert envelope.payload.serialized_payload_b64 is not None
    assert envelope.fee_estimate == 5000

    # 5. Simulation
    adapter = SolanaSimulationAdapter(transaction_builder=builder)
    result = await adapter.execute_to_result(plan)

    # 6. Assertions
    assert result.status == "filled"
    assert result.simulated is True
    assert result.adapter == "solana_simulation"
    assert result.quantity_executed == Decimal("100.0")
    assert result.average_price == Decimal("100.0")

    # Receipt Check
    receipt = result.metadata["receipt"]
    assert receipt["success"] is True
    assert receipt["transaction_hash"].startswith("sim_")
    assert receipt["metadata"]["envelope_fingerprint"] == envelope.fingerprint()

    print(f"Demo SUCCESS: Transaction Hash {result.execution_id}")
    print(f"Fingerprint: {envelope.fingerprint()}")

if __name__ == "__main__":
    asyncio.run(test_full_solana_dry_run())
