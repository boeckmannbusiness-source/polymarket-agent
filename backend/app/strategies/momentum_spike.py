from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class MomentumSpikeConfig(StrategyConfig):
    min_momentum: float = Field(default=0.03, ge=0, description="Min absolute 1h momentum to trigger")
    volume_spike_ratio: float = Field(default=2.0, ge=1.0, description="5m volume vs expected ratio for confirmation")
    min_volume_5m: float = Field(default=100, ge=0, description="Min 5m volume to avoid noise")
    max_spread_ratio: float = Field(default=0.05, ge=0, le=1.0, description="Max allowable spread/mid ratio")


class MomentumSpikeStrategy(BaseStrategy):
    name = "momentum_spike"
    version = "1.0.0"
    description = "Detects rapid odds movements that may indicate momentum-driven price action"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = MomentumSpikeConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        momentum = market_state.get("momentum_1h")
        if momentum is None or abs(momentum) < self.cfg.min_momentum:
            return None

        current_price = market_state.get("current_price")
        if current_price is None or current_price <= 0:
            return None

        spread = market_state.get("spread", 0) or 0
        if spread > 0 and current_price > 0:
            spread_ratio = spread / current_price
            if spread_ratio > self.cfg.max_spread_ratio:
                return None

        volume_5m = market_state.get("volume_5m", 0) or 0
        if volume_5m < self.cfg.min_volume_5m:
            return None

        volume_1h = market_state.get("volume_1h", 0) or 0
        expected_5m = volume_1h / 12
        volume_confirmed = volume_5m > expected_5m * self.cfg.volume_spike_ratio

        is_up = momentum > 0
        direction = "BUY_YES" if is_up else "BUY_NO"

        abs_mom = min(abs(momentum), 0.5)
        confidence = 0.5 + (abs_mom * 2.0)
        if volume_confirmed:
            confidence += 0.15
        confidence = max(0.1, min(0.95, confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            market_id=market_state.get("market_id"),
            reason=f"Momentum {'surge' if is_up else 'dump'} {abs_mom*100:.1f}% in 1h (vol_5m={volume_5m:.0f}, confirmed={volume_confirmed})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime="momentum",
            strategy_version=self.version,
            feature_values={
                "momentum_1h": round(momentum, 4),
                "volume_5m": volume_5m,
                "volume_1h": volume_1h,
                "volume_confirmed": volume_confirmed,
                "spread_ratio": round(spread / current_price, 4) if spread > 0 and current_price > 0 else 0,
            },
        )
