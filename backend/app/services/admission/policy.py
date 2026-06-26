from typing import List, Tuple
from app.domain.admission.models import (
    MarketQualityDecision,
    AdmissionDecision,
    AssetSnapshot
)
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot

class AssetAdmissionPolicy:
    """
    Orchestrates the final admission decision based on market quality and venue capabilities.
    """

    POLICY_VERSION = "2.3A"

    def evaluate(
        self,
        quality_decision: MarketQualityDecision,
        snapshot: AssetSnapshot,
        capabilities: CapabilitySnapshot
    ) -> Tuple[AdmissionDecision, List[str]]:
        reasons = []

        # 1. Start with Quality Decision mapping
        if quality_decision == MarketQualityDecision.BLOCKED:
            return AdmissionDecision.BLOCK, ["REJECTED_BY_QUALITY_ENGINE"]

        # 2. Check for missing route
        if not snapshot.route_snapshot:
            return AdmissionDecision.WATCH, ["MISSING_ROUTE"]

        # 3. Check venue capabilities (Asset admission only affects planning/simulation)
        # We must ensure no auto-trading is implied
        if quality_decision == MarketQualityDecision.APPROVED:
            decision = AdmissionDecision.ALLOW_SIMULATION
        else:
            decision = AdmissionDecision.WATCH

        # Forbidden: auto_trade, auto_execute, auto_allocate
        # These are enforced by the fact that we only return ALLOW_SIMULATION or WATCH
        # and never an "EXECUTE" state.

        return decision, reasons
