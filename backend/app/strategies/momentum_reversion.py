from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class MomentumReversionConfig(StrategyConfig):
    min_momentum: float = Field(default=0.02, ge=0, description="Min absolute 1h momentum to consider a move stretched")
    price_extreme_high: float = Field(default=0.75, ge=0.5, le=1.0, description="Above this YES price, fade rally -> BUY_NO")
    price_extreme_low: float = Field(default=0.25, ge=0.0, le=0.5, description="Below this YES price, fade selloff -> BUY_YES")
    min_volume_5m: float = Field(default=50, ge=0, description="Min 5m volume to avoid noise")
    max_spread_ratio: float = Field(default=0.05, ge=0, le=1.0, description="Max allowable spread/mid ratio")


class MomentumReversionStrategy(BaseStrategy):
    name = "momentum_reversion"
    version = "1.0.0"
    description = "Fades overstretched momentum moves near price extremes (mean reversion)"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = MomentumReversionConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        price = market_state.get("current_price")
        if price is None or price <= 0:
            return None

        momentum = market_state.get("momentum_1h")
        if momentum is None:
            return None

        volume_5m = market_state.get("volume_5m", 0) or 0
        if volume_5m < self.cfg.min_volume_5m:
            return None

        spread = market_state.get("spread", 0) or 0
        if spread > 0 and price > 0:
            if spread / price > self.cfg.max_spread_ratio:
                return None

        abs_mom = abs(momentum)
        if abs_mom < self.cfg.min_momentum:
            return None

        direction = None
        confidence = 0.0
        reason = ""

        if price > self.cfg.price_extreme_high and momentum > self.cfg.min_momentum:
            direction = "BUY_NO"
            stretch = (price - 0.5) * 2.0
            confidence = 0.3 + stretch * 0.3 + abs_mom * 2.0
            reason = f"Fade rally at {price:.2f} (mom={momentum:+.4f}, stretch={stretch:.2f})"

        elif price < self.cfg.price_extreme_low and momentum < -self.cfg.min_momentum:
            direction = "BUY_YES"
            stretch = (0.5 - price) * 2.0
            confidence = 0.3 + stretch * 0.3 + abs_mom * 2.0
            reason = f"Fade selloff at {price:.2f} (mom={momentum:+.4f}, stretch={stretch:.2f})"

        if direction is None:
            return None

        entropy = market_state.get("entropy")
        if entropy is not None:
            if entropy < 0.5:
                confidence += 0.1

        confidence = max(0.1, min(0.95, confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=reason,
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime=market_state.get("regime", "unknown"),
            strategy_version=self.version,
            feature_values={
                "current_price": price,
                "momentum_1h": round(momentum, 4),
                "volume_5m": volume_5m,
                "entropy": entropy,
                "price_zone": market_state.get("price_zone"),
                "distance_to_0.5": market_state.get("distance_to_0.5"),
                "regime": market_state.get("regime"),
            },
        )
