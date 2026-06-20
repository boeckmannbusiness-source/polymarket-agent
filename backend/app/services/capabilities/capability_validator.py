from typing import List
from app.domain.capabilities import VenueCapability, VenueCapabilities, CapabilityReport
from app.domain.execution import ExecutionIntent, ExecutionResult
from app.domain.planning.transaction_plan import TransactionPlan


class CapabilityValidator:
    def validate_intent(self, intent: ExecutionIntent, capabilities: VenueCapabilities) -> CapabilityReport:
        report = CapabilityReport()

        # Basic check: Venue supports execution
        if not capabilities.has(VenueCapability.EXECUTION):
            report.missing.append(VenueCapability.EXECUTION.value)
        else:
            report.supported.append(VenueCapability.EXECUTION.value)

        # Replay capability check
        if capabilities.has(VenueCapability.REPLAY):
            report.supported.append(VenueCapability.REPLAY.value)

        # Market resolution check
        if capabilities.has(VenueCapability.MARKET_RESOLUTION):
            report.supported.append(VenueCapability.MARKET_RESOLUTION.value)

        return report

    def validate_plan(self, plan: TransactionPlan, capabilities: VenueCapabilities) -> CapabilityReport:
        report = CapabilityReport()

        if not capabilities.has(VenueCapability.QUOTE):
            report.missing.append(VenueCapability.QUOTE.value)
        else:
            report.supported.append(VenueCapability.QUOTE.value)

        if plan.route:
            if not capabilities.has(VenueCapability.ROUTING):
                report.missing.append(VenueCapability.ROUTING.value)
            else:
                report.supported.append(VenueCapability.ROUTING.value)

            if len(plan.route.hops if hasattr(plan.route, "hops") else []) > 1:
                if not capabilities.has(VenueCapability.MULTI_HOP):
                    report.missing.append(VenueCapability.MULTI_HOP.value)
                else:
                    report.supported.append(VenueCapability.MULTI_HOP.value)

        if plan.instructions:
            if not capabilities.has(VenueCapability.TRANSACTION_BUILDING):
                report.missing.append(VenueCapability.TRANSACTION_BUILDING.value)
            else:
                report.supported.append(VenueCapability.TRANSACTION_BUILDING.value)

        if hasattr(plan, "slippage_bps") and plan.slippage_bps is not None:
            if capabilities.has(VenueCapability.SLIPPAGE_MODEL):
                report.supported.append(VenueCapability.SLIPPAGE_MODEL.value)

        return report

    def validate_result(self, result: ExecutionResult, capabilities: VenueCapabilities) -> CapabilityReport:
        report = CapabilityReport()

        if result.simulated and not capabilities.has(VenueCapability.SIMULATION):
            report.missing.append(VenueCapability.SIMULATION.value)
        else:
            if result.simulated:
                report.supported.append(VenueCapability.SIMULATION.value)

        if result.instruction_trace and not capabilities.has(VenueCapability.TRANSACTION_BUILDING):
             report.warnings.append("Execution produced instruction trace but venue lacks TRANSACTION_BUILDING capability")

        if capabilities.has(VenueCapability.PORTFOLIO_FEEDBACK):
            report.supported.append(VenueCapability.PORTFOLIO_FEEDBACK.value)

        if result.quantity_executed and result.quantity_executed < (result.metadata.get("requested_quantity") if result.metadata else result.quantity_executed):
             if not capabilities.has(VenueCapability.PARTIAL_FILL):
                 report.warnings.append("Partial fill detected but venue lacks PARTIAL_FILL capability")
             else:
                 report.supported.append(VenueCapability.PARTIAL_FILL.value)

        return report

    @classmethod
    def covered_capabilities(cls) -> List[VenueCapability]:
        # Return all capabilities that are integrated into validation logic
        return [c for c in VenueCapability]
