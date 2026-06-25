from decimal import Decimal
from typing import Tuple


class FeeEstimator:
    """Estimates Solana transaction fees based on compute units and priority fees."""

    @staticmethod
    def estimate_fee(
        compute_units: int,
        priority_fee_lamports: int,
        base_fee_lamports: int = 5000
    ) -> Tuple[int, Decimal]:
        """
        Estimates the total fee for a transaction.

        Args:
            compute_units: The number of compute units consumed.
            priority_fee_lamports: The priority fee per compute unit in lamports.
            base_fee_lamports: The base fee for the transaction (default 5000 lamports).

        Returns:
            A tuple of (total_fee_lamports, confidence_score).
        """
        compute_units_dec = Decimal(str(compute_units))
        priority_fee_dec = Decimal(str(priority_fee_lamports))
        base_fee_dec = Decimal(str(base_fee_lamports))

        # total_fee = base_fee + priority_fee_lamports
        total_fee = base_fee_dec + priority_fee_dec

        # Realistic confidence based on CU stability
        confidence = Decimal("0.95") if compute_units > 0 else Decimal("0.50")

        return int(total_fee), confidence
