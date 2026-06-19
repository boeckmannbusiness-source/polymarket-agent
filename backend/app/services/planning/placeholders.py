from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.transaction_instruction import TransactionInstruction
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.quote_provider import QuoteProvider
from app.services.planning.route_planner import RoutePlanner
from app.services.planning.transaction_builder import TransactionBuilder
from app.services.planning.planner import Planner


class PlaceholderQuoteProvider(QuoteProvider):
    async def get_quote(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
    ) -> Quote:
        max_slippage = constraints.max_slippage_bps if constraints else 100
        return Quote(
            instrument=instrument,
            amount_in=amount_in,
            expected_amount_out=amount_in,
            estimated_price=Decimal("0"),
            slippage_bps=max_slippage,
            source="placeholder",
            timestamp=datetime.now(timezone.utc),
            source_latency_ms=0.0,
            venue_hint=instrument.venue,
        )


class PlaceholderRoutePlanner(RoutePlanner):
    async def build_route(
        self,
        quote: Quote,
        constraints: ExecutionConstraints | None = None,
    ) -> Route:
        return Route(
            venue=quote.instrument.venue,
            hops=[quote.instrument.venue],
            route_type="DIRECT",
            estimated_latency_ms=0,
            estimated_cost_bps=5,
            price_impact_estimate=quote.price_impact_estimate,
        )


class PlaceholderTransactionBuilder(TransactionBuilder):
    async def build(
        self,
        quote: Quote,
        route: Route,
        constraints: ExecutionConstraints | None = None,
    ) -> TransactionPlan:
        resolved = constraints or ExecutionConstraints(max_slippage_bps=100)
        now = datetime.now(timezone.utc)
        instructions = [
            TransactionInstruction(
                instruction_type="SWAP",
                source_asset=quote.instrument.asset_identifier,
                target_asset=quote.instrument.quote_asset,
                amount=quote.amount_in,
                metadata={"hop_index": 0, "venue": route.venue},
            )
        ]
        return TransactionPlan(
            quote=quote,
            route=route,
            constraints=resolved,
            instructions=instructions,
            estimated_fees=5000,
            slippage_bps=resolved.max_slippage_bps,
            execution_deadline=now + timedelta(seconds=120),
        )


def create_default_planner() -> Planner:
    return Planner(
        quote_provider=PlaceholderQuoteProvider(),
        route_planner=PlaceholderRoutePlanner(),
        transaction_builder=PlaceholderTransactionBuilder(),
    )


def create_live_planner() -> Planner:
    """Creates a fully live Planner with real quote, route, and transaction construction.

    All three planning layers are real implementations.
    NO execution, NO signing, NO swap calls.
    """
    from app.services.planning.providers.jupiter_quote_provider import JupiterQuoteProvider
    from app.services.planning.route_planner import JupiterRoutePlanner
    from app.services.planning.transaction_builder import JupiterTransactionBuilder
    return Planner(
        quote_provider=JupiterQuoteProvider(),
        route_planner=JupiterRoutePlanner(),
        transaction_builder=JupiterTransactionBuilder(),
    )
