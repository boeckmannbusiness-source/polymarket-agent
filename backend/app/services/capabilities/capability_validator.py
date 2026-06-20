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

        # If it has a transaction plan already (e.g. from planner), it might have used routing
        if intent.metadata and "transaction_plan" in intent.metadata:
            # We don't have the plan here easily unless it's in intent.
            # Usually intent is built before planning or contains plan.
            pass

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

        return report

    def validate_result(self, result: ExecutionResult, capabilities: VenueCapabilities) -> CapabilityReport:
        report = CapabilityReport()

        if result.simulated and not capabilities.has(VenueCapability.SIMULATION):
            report.missing.append(VenueCapability.SIMULATION.value)

        if result.instruction_trace and not capabilities.has(VenueCapability.TRANSACTION_BUILDING):
             report.warnings.append("Execution produced instruction trace but venue lacks TRANSACTION_BUILDING capability")

        return report
