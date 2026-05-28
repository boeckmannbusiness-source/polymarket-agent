from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class SpreadCompressionConfig(StrategyConfig):
    max_spread_ratio: float = Field(default=0.01, ge=0, description="Spread ratio below this is considered compressed")
    min_volume_5m: float = Field(default=100, ge=0)
    min_orderbook_imbalance: float = Field(default=0.2, ge=0, le=1.0)


class SpreadCompressionStrategy(BaseStrategy):
    name = "spread_compression"
    version = "1.0.0"
    description = "Detects compressed spreads + orderbook imbalance + volume confirmation"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = SpreadCompressionConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        price = market_state.get("current_price")
        if price is None or price <= 0:
            return None

        spread = market_state.get("spread", 0) or 0
        spread_ratio = spread / price if price > 0 and spread > 0 else 0
        if spread > 0 and spread_ratio > self.cfg.max_spread_ratio:
            return None

        volume_5m = market_state.get("volume_5m", 0) or 0
        if volume_5m < self.cfg.min_volume_5m:
            return None

        ob_imbalance = market_state.get("orderbook_imbalance", 0) or 0
        if abs(ob_imbalance) < self.cfg.min_orderbook_imbalance:
            return None

        direction = "BUY_YES" if ob_imbalance > 0 else "BUY_NO"
        confidence = 0.4 + abs(ob_imbalance) * 0.3
        confidence = min(0.95, confidence)

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=f"Spread compressed ({spread_ratio:.4f}) + orderbook imbalance ({ob_imbalance:+.3f})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime=market_state.get("regime", "unknown"),
            strategy_version=self.version,
            feature_values={
                "current_price": price,
                "spread_ratio": round(spread_ratio, 4),
                "volume_5m": volume_5m,
                "orderbook_imbalance": ob_imbalance,
                "regime": market_state.get("regime"),
            },
        )
