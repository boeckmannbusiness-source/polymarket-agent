from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.services.planning.quote_provider import QuoteProvider
from app.services.planning.route_planner import RoutePlanner
from app.services.planning.transaction_builder import TransactionBuilder


class Planner:
    def __init__(
        self,
        quote_provider: QuoteProvider,
        route_planner: RoutePlanner,
        transaction_builder: TransactionBuilder,
    ):
        self._quote_provider = quote_provider
        self._route_planner = route_planner
        self._transaction_builder = transaction_builder

    async def plan(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
    ) -> TransactionPlan:
        quote = await self._quote_provider.get_quote(instrument, amount_in, side, constraints)
        route = await self._route_planner.build_route(quote, constraints)
        plan = await self._transaction_builder.build(quote, route, constraints)
        return plan
