from decimal import Decimal

from app.domain.planning.quote import Quote
from app.domain.planning.route import Route, RouteType
from app.domain.planning.execution_constraints import ExecutionConstraints


SINGLE_HOP_COST_BPS = 5
SPLIT_HOP_COST_BPS = 12
HIGH_IMPACT_THRESHOLD = 0.02  # 2% price impact considered high
HIGH_LATENCY_THRESHOLD_MS = 500
SPLIT_PREFERENCE_DEPTH_RATIO = Decimal("0.3")  # if liquidity < 30% of amount, consider split


class RouteOptimizer:
    """Computes optimal trade route based on quote and constraints.

    Decision rules:
    - Prefer lowest price impact
    - Prefer lowest latency
    - Prefer single-hop unless cost > threshold
    - Support splitting logic (SIMULATED ONLY)
    """

    @staticmethod
    def select_best_route(
        quote: Quote,
        constraints: ExecutionConstraints | None = None,
    ) -> Route:
        venue = quote.venue_hint or quote.instrument.venue
        liquidity = quote.liquidity_depth or Decimal("0")
        amount = quote.amount_in
        impact = quote.price_impact_estimate or 0.0
        latency = quote.source_latency_ms or 0.0

        if RouteOptimizer._should_split(amount, liquidity, impact, constraints):
            return RouteOptimizer._build_split_route(venue, quote, amount, liquidity, impact)
        else:
            return RouteOptimizer._build_direct_route(venue, impact, latency, constraints)

    @staticmethod
    def _should_split(
        amount: Decimal,
        liquidity: Decimal,
        impact: float,
        constraints: ExecutionConstraints | None,
    ) -> bool:
        if constraints and constraints.require_atomic_execution:
            return False
        if liquidity > Decimal("0") and amount > liquidity * (Decimal("1") / SPLIT_PREFERENCE_DEPTH_RATIO):
            return True
        if impact > HIGH_IMPACT_THRESHOLD:
            return True
        return False

    @staticmethod
    def _build_direct_route(
        venue: str,
        impact: float,
        latency: float,
        constraints: ExecutionConstraints | None,
    ) -> Route:
        max_latency = constraints.max_latency_ms if constraints else None
        route_type: RouteType = "DIRECT"

        if max_latency and latency > max_latency:
            route_type = "OPTIMIZED"

        return Route(
            venue=venue,
            hops=[venue],
            route_type=route_type,
            estimated_latency_ms=latency,
            estimated_cost_bps=SINGLE_HOP_COST_BPS,
            price_impact_estimate=impact,
        )

    @staticmethod
    def _build_split_route(
        venue: str,
        quote: Quote,
        amount: Decimal,
        liquidity: Decimal,
        impact: float,
    ) -> Route:
        half = amount / Decimal("2")
        split_impact = impact * 0.6  # simulated: splitting halves impact

        return Route(
            venue=venue,
            hops=[venue, venue],
            route_type="SPLIT",
            estimated_latency_ms=(quote.source_latency_ms or 0) * 1.5,
            estimated_cost_bps=SPLIT_HOP_COST_BPS,
            price_impact_estimate=split_impact,
            metadata={"split_1": str(half), "split_2": str(half)},
        )

    @staticmethod
    def estimate_cost(route: Route, quote: Quote) -> int:
        base = route.estimated_cost_bps or 0
        if route.route_type == "SPLIT":
            base += SPLIT_HOP_COST_BPS - SINGLE_HOP_COST_BPS
        return base
