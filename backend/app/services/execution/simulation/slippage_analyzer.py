from decimal import Decimal
from typing import Tuple


class SlippageAnalyzer:
    """Analyzes effective slippage and categorizes risk."""

    @staticmethod
    def analyze_slippage(
        expected_out: Decimal,
        simulated_out: Decimal,
        fee: Decimal = Decimal("0"),
        slippage_bps_threshold: int = 100
    ) -> Tuple[Decimal, str]:
        """
        Calculates effective slippage and determines if it's within acceptable bounds.

        Args:
            expected_out: The expected output amount from the planner/quote.
            simulated_out: The actual output amount from the simulation.
            fee: Estimated fee in lamports.
            slippage_bps_threshold: The maximum allowed slippage in basis points.

        Returns:
            A tuple of (effective_slippage_bps, status).
            Status can be "LOW", "MEDIUM", "HIGH", or "REJECT".
        """
        if expected_out <= 0:
            return Decimal("0"), "UNKNOWN"

        # effective_slippage = (expected - simulated) / expected
        diff = expected_out - simulated_out
        slippage_ratio = diff / expected_out
        slippage_bps = slippage_ratio * Decimal("10000")

        threshold_dec = Decimal(str(slippage_bps_threshold))

        if slippage_bps < 0:
            # Price improvement
            return slippage_bps, "LOW"

        if slippage_bps <= (threshold_dec * Decimal("0.2")):
            return slippage_bps, "LOW"
        elif slippage_bps <= (threshold_dec * Decimal("0.5")):
            return slippage_bps, "MEDIUM"
        elif slippage_bps <= threshold_dec:
            return slippage_bps, "HIGH"
        else:
            return slippage_bps, "REJECT"
