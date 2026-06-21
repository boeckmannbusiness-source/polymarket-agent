import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.shadow.pricing.registry import PriceResolverRegistry
from app.services.shadow.pricing.resolver import PriceResolver
from app.services.shadow.shadow_execution_service import ShadowExecutionService, ShadowExecution

@pytest.mark.asyncio
async def test_venue_based_resolver_selection():
    solana_resolver = MagicMock(spec=PriceResolver)
    solana_resolver.resolve_price = AsyncMock(return_value=1.5)
    poly_resolver = MagicMock(spec=PriceResolver)
    poly_resolver.resolve_price = AsyncMock(return_value=0.5)
    PriceResolverRegistry.clear()
    PriceResolverRegistry.register("jupiter", solana_resolver)
    PriceResolverRegistry.register("polymarket", poly_resolver)
    service = ShadowExecutionService()
    sol_exec = ShadowExecution(
        id="sol1", signal_id="s1", market_id="So11111111111111111111111111111111111111112",
        strategy="s", direction="buy", outcome=None, size=10, entry_price=1.0, status="open"
    )
    poly_exec = ShadowExecution(
        id="poly1", signal_id="s2", market_id="0x123",
        strategy="s", direction="buy", outcome="YES", size=10, entry_price=0.4, status="open"
    )
    service._executions = {"sol1": sol_exec, "poly1": poly_exec}
    await service.refresh_prices(None)
    assert solana_resolver.resolve_price.called
    assert poly_resolver.resolve_price.called
    sol_call_res = solana_resolver.resolve_price.call_args[0][0]
    assert sol_call_res.asset.asset_id.venue == "jupiter"
    poly_call_res = poly_resolver.resolve_price.call_args[0][0]
    assert poly_call_res.asset.asset_id.venue == "polymarket"

def test_no_binary_branching_in_resolver_selection():
    import inspect
    from app.services.shadow.shadow_execution_service import ShadowExecutionService
    source = inspect.getsource(ShadowExecutionService.refresh_prices)
    forbidden = ["if outcome", "if \"YES\"", "if 'YES'", "if \"NO\"", "if 'NO'"]
    for word in forbidden:
        assert word not in source, f"Forbidden binary branching found in refresh_prices: {word}"
    assert "PriceResolverRegistry.get(venue)" in source
