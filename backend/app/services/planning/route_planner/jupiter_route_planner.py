from app.domain.planning.quote import Quote
from app.domain.planning.route import Route
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.route_planner.base_route_planner import RoutePlanner
from app.services.planning.route_planner.route_optimizer import RouteOptimizer


class JupiterRoutePlanner(RoutePlanner):
    """Route planner for Jupiter-compatible venues.

    Computes optimal execution route based on quote data.
    READ-ONLY simulation — no swaps, no execution, no signing.
    """

    def __init__(self, optimizer: RouteOptimizer | None = None):
        self._optimizer = optimizer or RouteOptimizer()

    async def build_route(
        self,
        quote: Quote,
        constraints: ExecutionConstraints | None = None,
    ) -> Route:
        return self._optimizer.select_best_route(quote, constraints)
