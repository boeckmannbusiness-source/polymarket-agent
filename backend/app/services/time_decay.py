import math

from app.config import settings


class TimeDecayService:
    def __init__(self, half_life_hours: float | None = None, saturation_trades: int | None = None):
        self.half_life_hours = half_life_hours or settings.SOLANA_RECENCY_HALF_LIFE_HOURS
        self.saturation_trades = saturation_trades or settings.SOLANA_FREQUENCY_SATURATION_TRADES

    def decay_recency(self, hours_since_event: float) -> float:
        """Exponential decay of recency.

        Args:
            hours_since_event: Time elapsed in HOURS (not seconds, not timestamps).
                               Negative values treated as 0 (event is now or future).

        Returns:
            float in [0, 1]. 1.0 = maximally recent, approaches 0 as time passes.
        """
        if hours_since_event < 0:
            return 1.0
        lam = math.log(2) / self.half_life_hours
        return max(0.0, min(1.0, math.exp(-lam * hours_since_event)))

    def decay_frequency(self, raw_count: int | float) -> float:
        if raw_count < 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - math.exp(-raw_count / self.saturation_trades)))