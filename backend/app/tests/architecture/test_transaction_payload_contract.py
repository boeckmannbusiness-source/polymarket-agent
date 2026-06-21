import pytest
import base64
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.execution.instrument import Instrument
from decimal import Decimal

def _make_dummy_quote():
    return Quote(
        instrument=Instrument(
            venue="jupiter",
            symbol="SOL",
            asset_identifier="So11111111111111111111111111111111111111112",
            quote_asset="USDC"
        ),
        amount_in=Decimal("1.0"),
        expected_amount_out=Decimal("100.0"),
        estimated_price=Decimal("100.0"),
        slippage_bps=50,
        source="jupiter"
    )

def test_transaction_plan_payload_contract():
    payload = b"dummy_solana_transaction_data"
    payload_b64 = base64.b64encode(payload).decode("utf-8")
    plan = TransactionPlan(
        quote=_make_dummy_quote(),
        route=Route(venue="jupiter", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=50, max_latency_ms=1000),
        serialized_payload_b64=payload_b64
    )
    assert plan.serialized_payload_b64 == payload_b64
    json_data = plan.model_dump_json()
    assert payload_b64 in json_data

def test_simulation_stability_with_payload():
    constraints = ExecutionConstraints(max_slippage_bps=50)
    plan_with = TransactionPlan(
        quote=_make_dummy_quote(),
        route=Route(venue="jupiter", hops=[]),
        constraints=constraints,
        serialized_payload_b64="YmFzZTY0"
    )
    plan_without = TransactionPlan(
        quote=_make_dummy_quote(),
        route=Route(venue="jupiter", hops=[]),
        constraints=constraints
    )
    assert plan_with.quote == plan_without.quote
    assert plan_with.constraints == plan_without.constraints
