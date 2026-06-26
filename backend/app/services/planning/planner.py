from decimal import Decimal

from app.domain.execution.instrument import Instrument
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.planning.execution_constraints import ExecutionConstraints
from app.domain.assets import AssetResolution
from app.services.planning.quote_provider import QuoteProvider
from app.services.planning.route_planner import RoutePlanner
from app.services.planning.transaction_builder import TransactionBuilder
from app.services.capabilities import CapabilityResolver, CapabilityValidator
from app.services.admission.admission_service import AdmissionService
from app.domain.admission.models import AssetSnapshot, AdmissionDecision
from app.core.logging import logger
from app.services.audit.audit_logger import emit


class Planner:
    def __init__(
        self,
        quote_provider: QuoteProvider,
        route_planner: RoutePlanner,
        transaction_builder: TransactionBuilder,
        admission_service: AdmissionService | None = None,
    ):
        self._quote_provider = quote_provider
        self._route_planner = route_planner
        self._transaction_builder = transaction_builder
        self._capability_resolver = CapabilityResolver()
        self._capability_validator = CapabilityValidator()
        self._admission_service = admission_service or AdmissionService()

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

        # Asset Admission Check
        if asset_resolution:
            await self._check_admission(asset_resolution, capabilities, **kwargs)

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

    async def _check_admission(self, asset_resolution, capabilities, **kwargs):
        # In a real scenario, we would fetch market data here to create the snapshot.
        # For now, we'll assume the snapshot is provided in kwargs or create a placeholder.
        snapshot = kwargs.get("asset_snapshot")
        if not snapshot:
             # Placeholder snapshot if not provided - in production this would be real data
             snapshot = AssetSnapshot(
                 asset_id=asset_resolution.asset_id,
                 symbol=asset_resolution.asset_id.symbol,
                 venue=asset_resolution.asset_id.venue,
                 market_cap=Decimal("0"),
                 liquidity=Decimal("0"),
                 asset_age_days=0,
                 evaluation_slot=kwargs.get("slot", 0)
             )

        receipt = await self._admission_service.admit_asset(snapshot, capabilities)

        if receipt.decision == AdmissionDecision.BLOCK:
            logger.error("asset_admission_blocked",
                         asset_id=asset_resolution.asset_id.canonical_id,
                         reasons=receipt.reasons)
            raise ValueError(f"Asset {asset_resolution.asset_id.canonical_id} is BLOCKED from planning: {receipt.reasons}")

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
