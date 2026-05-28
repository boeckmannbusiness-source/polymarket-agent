from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class LiquidityVacuumConfig(StrategyConfig):
    min_trade_size: float = Field(default=300, ge=0)
    min_volume_ratio: float = Field(default=1.5, ge=1.0)
    max_spread_ratio: float = Field(default=0.03, ge=0, le=1.0)


class LiquidityVacuumStrategy(BaseStrategy):
    name = "liquidity_vacuum"
    version = "1.0.0"
    description = "Detects markets where liquidity is being rapidly consumed, suggesting impending price moves"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = LiquidityVacuumConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        size = float(market_state.get("size", 0) or 0)
        if size < self.cfg.min_trade_size:
            return None

        volume_5m = market_state.get("volume_5m", 0) or 0
        volume_1h = market_state.get("volume_1h", 0) or 0
        expected_5m = volume_1h / 12 if volume_1h > 0 else 1

        if expected_5m > 0 and volume_5m / expected_5m < self.cfg.min_volume_ratio:
            return None

        current_price = market_state.get("current_price")
        if current_price is None or current_price <= 0:
            return None

        spread = market_state.get("spread", 0) or 0
        spread_ratio = spread / current_price if spread > 0 and current_price > 0 else 0
        if spread > 0 and spread_ratio > self.cfg.max_spread_ratio:
            return None

        side = market_state.get("side", "buy")
        direction = "BUY_YES" if side.upper() in ("BUY", "YES") else "BUY_NO"

        volume_ratio = volume_5m / expected_5m if expected_5m > 0 else 1.0
        size_factor = min(size / 5000, 1.0)
        confidence = 0.4 + (volume_ratio * 0.1) + (size_factor * 0.2)
        confidence = max(0.1, min(0.9, confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=f"Liquidity vacuum: {size:.0f} trade at {volume_ratio:.1f}x expected volume (spread={spread_ratio:.4f})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime=market_state.get("regime", "normal"),
            strategy_version=self.version,
            feature_values={
                "trade_size": size,
                "volume_5m": volume_5m,
                "volume_1h": volume_1h,
                "volume_ratio": round(volume_ratio, 2),
                "spread_ratio": round(spread_ratio, 4),
            },
        )
