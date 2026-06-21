import pytest
from app.domain.execution.execution_intent import ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.execution.instrument import Instrument
from app.services.planning.planner import Planner
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

def test_slippage_field_locations():
    intent = ExecutionIntent(
        instrument=Instrument(venue="v", symbol="S", asset_identifier="id", quote_asset="Q"),
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        slippage_bps=100
    )
    assert intent.slippage_bps == 100
    from app.domain.planning.quote import Quote
    from app.domain.planning.route import Route
    from app.domain.planning.execution_constraints import ExecutionConstraints
    plan = TransactionPlan(
        quote=Quote(
            instrument=intent.instrument, amount_in=Decimal("1"), expected_amount_out=Decimal("1"),
            estimated_price=Decimal("1"), slippage_bps=100, source="s"
        ),
        route=Route(venue="v", hops=[]),
        constraints=ExecutionConstraints(max_slippage_bps=100),
        slippage_bps=100
    )
    assert plan.slippage_bps == 100

@pytest.mark.asyncio
async def test_planner_slippage_propagation():
    quote_provider = MagicMock()
    route_planner = MagicMock()
    transaction_builder = MagicMock()
    with patch("app.services.capabilities.CapabilityResolver.resolve") as mock_resolve, \
         patch("app.services.capabilities.CapabilityValidator.validate_plan") as mock_validate:
        mock_capabilities = MagicMock()
        mock_capabilities.venue = "jupiter"
        mock_resolve.return_value = mock_capabilities
        mock_report = MagicMock()
        mock_report.is_valid = True
        mock_validate.return_value = mock_report
        planner = Planner(quote_provider, route_planner, transaction_builder)
        instrument = Instrument(venue="jupiter", symbol="SOL", asset_identifier="id", quote_asset="USDC")
        from app.domain.planning.quote import Quote
        from app.domain.planning.route import Route
        from app.domain.planning.transaction_plan import TransactionPlan
        from app.domain.planning.execution_constraints import ExecutionConstraints
        mock_quote = Quote(
            instrument=instrument, amount_in=Decimal("1"), expected_amount_out=Decimal("100"),
            estimated_price=Decimal("100"), slippage_bps=50, source="jupiter"
        )
        quote_provider.get_quote = AsyncMock(return_value=mock_quote)
        mock_route = Route(venue="jupiter", hops=[])
        route_planner.build_route = AsyncMock(return_value=mock_route)
        constraints = ExecutionConstraints(max_slippage_bps=50)
        mock_plan = TransactionPlan(
            quote=mock_quote,
            route=mock_route,
            constraints=constraints,
            slippage_bps=50
        )
        transaction_builder.build = AsyncMock(return_value=mock_plan)
        plan = await planner.plan(instrument, Decimal("1"), "buy", constraints)
        assert plan.slippage_bps == 50
        assert transaction_builder.build.called
        assert transaction_builder.build.call_args[0][2].max_slippage_bps == 50
