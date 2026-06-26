from decimal import Decimal
from typing import Tuple, List
from app.domain.admission.models import AssetSnapshot, MarketQualityDecision

class MarketQualityEngine:
    """
    Evaluates asset market quality using deterministic signals from an AssetSnapshot.
    """

    # Thresholds for evaluation
    MIN_MARKET_CAP = Decimal("1000000")  # $1M
    MIN_LIQUIDITY = Decimal("50000")     # $50k
    MAX_HOLDER_CONCENTRATION = Decimal("0.25") # 25% for top holder
    MIN_ASSET_AGE_DAYS = 7
    MIN_ROUTE_CONFIDENCE = Decimal("0.80")

    def evaluate(self, snapshot: AssetSnapshot) -> Tuple[MarketQualityDecision, List[str]]:
        reasons = []

        # 1. Market Cap Check
        if snapshot.market_cap < self.MIN_MARKET_CAP:
            reasons.append("LOW_MARKET_CAP")

        # 2. Liquidity Check
        if snapshot.liquidity < self.MIN_LIQUIDITY:
            reasons.append("LOW_LIQUIDITY")

        # 3. Holder Concentration Check
        # Assuming holder_distribution contains percentage held by top accounts
        for holder, percentage in snapshot.holder_distribution.items():
            if percentage > self.MAX_HOLDER_CONCENTRATION:
                reasons.append("HIGH_CONCENTRATION")
                break

        # 4. Asset Age Check
        if snapshot.asset_age_days < self.MIN_ASSET_AGE_DAYS:
            reasons.append("NEW_ASSET")

        # 5. Route Confidence Check
        # Extract confidence from route_snapshot if present
        route_confidence = Decimal(str(snapshot.route_snapshot.get("confidence", "0")))
        if route_confidence < self.MIN_ROUTE_CONFIDENCE:
            reasons.append("LOW_ROUTE_CONFIDENCE")

        if "LOW_MARKET_CAP" in reasons or "LOW_LIQUIDITY" in reasons:
             return MarketQualityDecision.BLOCKED, reasons

        if reasons:
            return MarketQualityDecision.WATCH, reasons

        return MarketQualityDecision.APPROVED, []
