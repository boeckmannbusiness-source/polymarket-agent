import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.execution.instrument import Instrument
from app.services.execution.transaction_builder.solana_builder import SolanaTransactionBuilder

@pytest.mark.asyncio
async def test_determinism_x100():
    builder = SolanaTransactionBuilder()

    instr = TransactionInstruction(
        instruction_type="SWAP",
        source_asset="SOL",
        target_asset="USDC",
        amount=Decimal("1.0")
    )

    quote = Quote(
        instrument=Instrument(venue="jupiter", symbol="SOL/USDC", asset_identifier="SOL", quote_asset="USDC"),
        amount_in=Decimal("1.0"),
        expected_amount_out=Decimal("100.0"),
        estimated_price=Decimal("100.0"),
        slippage_bps=100,
        source="jupiter",
        timestamp=datetime.now(timezone.utc)
    )

    plan = TransactionPlan(
        quote=quote,
        route=Route(venue="jupiter", route_type="DIRECT", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=100),
        instructions=[instr],
        estimated_fees=5000,
        slippage_bps=100
    )

    fingerprints = []
    for _ in range(100):
        env = await builder.build_envelope(plan)
        fingerprints.append(env.fingerprint())

    # All fingerprints must be identical
    assert len(set(fingerprints)) == 1
    print(f"Deterministic fingerprint verified across 100 runs: {fingerprints[0]}")

if __name__ == "__main__":
    asyncio.run(test_determinism_x100())
