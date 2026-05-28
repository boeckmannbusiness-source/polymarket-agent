from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class NewsRepricingConfig(StrategyConfig):
    min_momentum_abs: float = Field(default=0.02, ge=0)
    min_volume_5m: float = Field(default=500, ge=0)
    volume_spike_ratio: float = Field(default=3.0, ge=1.0)
    max_wallet_score: float = Field(default=0.7, ge=0, le=1.0)


class NewsRepricingStrategy(BaseStrategy):
    name = "news_repricing"
    version = "1.0.0"
    description = "Detects price movements correlated with external news events or social sentiment"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = NewsRepricingConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        current_price = market_state.get("current_price")
        if current_price is None or current_price <= 0:
            return None

        momentum = market_state.get("momentum_1h")
        if momentum is None or abs(momentum) < self.cfg.min_momentum_abs:
            return None

        volume_5m = market_state.get("volume_5m", 0) or 0
        if volume_5m < self.cfg.min_volume_5m:
            return None

        volume_1h = market_state.get("volume_1h", 0) or 0
        expected_5m = volume_1h / 12 if volume_1h > 0 else 1
        if expected_5m > 0 and volume_5m / expected_5m < self.cfg.volume_spike_ratio:
            return None

        wallet_score = market_state.get("wallet_score")
        if wallet_score is not None and wallet_score > self.cfg.max_wallet_score:
            return None

        side = market_state.get("side", "buy")
        is_up = momentum > 0
        direction = "BUY_YES" if is_up else "BUY_NO"

        abs_mom = min(abs(momentum), 0.3)
        volume_ratio = volume_5m / expected_5m if expected_5m > 0 else 1.0
        confidence = 0.3 + (abs_mom * 3.0) + (min(volume_ratio, 5.0) * 0.05)
        confidence = max(0.1, min(0.9, confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=f"News repricing signal: {abs_mom*100:.1f}% move at {volume_ratio:.1f}x volume (side={side.upper()})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime=market_state.get("regime", "normal"),
            strategy_version=self.version,
            feature_values={
                "momentum_1h": round(momentum, 4),
                "volume_5m": volume_5m,
                "volume_1h": volume_1h,
                "volume_ratio": round(volume_ratio, 2),
                "wallet_score": wallet_score,
            },
        )
