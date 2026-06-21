from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.assets import AssetResolution
from app.services.planning.quote_provider import QuoteProvider
from app.services.planning.route_planner import RoutePlanner
from app.services.planning.transaction_builder import TransactionBuilder
from app.services.capabilities import CapabilityResolver, CapabilityValidator
from app.core.logging import logger
from app.services.audit.audit_logger import emit


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
        self._capability_resolver = CapabilityResolver()
        self._capability_validator = CapabilityValidator()

    async def plan(
        self,
        instrument: Instrument,
        amount_in: Decimal,
        side: str,
        constraints: ExecutionConstraints | None = None,
        asset_resolution: AssetResolution | None = None,
        quote_asset_resolution: AssetResolution | None = None,
        **kwargs,
    ) -> TransactionPlan:
        venue = instrument.venue
        capabilities = self._capability_resolver.resolve(venue)

        quote = await self._quote_provider.get_quote(
            instrument, amount_in, side, constraints, asset_resolution, quote_asset_resolution
        )
        await self._validate_quote(quote, capabilities)

        route = await self._route_planner.build_route(quote, constraints)
        await self._validate_route(route, capabilities)

        plan = await self._transaction_builder.build(quote, route, constraints)
        await self._validate_transaction(plan, capabilities)

        return plan

    async def _validate_quote(self, quote, capabilities):
        # Specific capability checks for quote if needed
        pass

    async def _validate_route(self, route, capabilities):
        # Specific capability checks for route if needed
        pass

    async def _validate_transaction(self, plan: TransactionPlan, capabilities):
        report = self._capability_validator.validate_plan(plan, capabilities)

        await emit("shadow.capability.validation", "capability", capabilities.venue, {
            "venue": capabilities.venue,
            "type": "plan",
            "is_valid": report.is_valid,
            "missing": report.missing,
            "supported": report.supported,
        })

        if not report.is_valid:
            logger.error("planner_capability_validation_failed", venue=capabilities.venue, missing=report.missing)
            raise ValueError(f"Venue {capabilities.venue} lacks required capabilities for plan: {report.missing}")
