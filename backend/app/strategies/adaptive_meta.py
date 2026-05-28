from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class AdaptiveMetaConfig(StrategyConfig):
    min_momentum: float = Field(default=0.015, ge=0)
    min_volume_5m: float = Field(default=50, ge=0)
    max_spread_ratio: float = Field(default=0.08, ge=0, le=1.0)
    crisis_reversion_threshold: float = Field(default=0.25, ge=0, le=0.5)
    extreme_continuation_threshold: float = Field(default=0.75, ge=0.5, le=1.0)
    high_volatility_threshold: float = Field(default=0.05, ge=0)
    mid_zone_orderbook_threshold: float = Field(default=0.15, ge=0, le=1.0)


class AdaptiveMetaStrategy(BaseStrategy):
    name = "adaptive_meta"
    version = "1.0.0"
    description = "State-conditional meta-strategy: mean-revert in crisis, continue in extreme, spread-compress in mid-zone"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = AdaptiveMetaConfig(**(config or {}))

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
        spread_ratio = spread / price if price > 0 and spread > 0 else 0
        if spread_ratio > self.cfg.max_spread_ratio:
            return None

        price_zone = market_state.get("price_zone", "fair")
        direction = None
        confidence = 0.0
        reason = ""
        regime = market_state.get("regime", "unknown")

        volatility = market_state.get("volatility_1h")

        if price_zone == "crisis" and momentum < -self.cfg.min_momentum:
            direction = "BUY_YES"
            stretch = (0.5 - price) * 2.0 if price < 0.5 else 0.0
            confidence = 0.4 + stretch * 0.3 + abs(momentum) * 1.5
            reason = f"Crisis reversion at {price:.4f} (mom={momentum:+.4f})"

        elif price_zone == "extreme":
            if momentum > self.cfg.min_momentum:
                direction = "BUY_YES"
                stretch = (price - 0.5) * 2.0
                confidence = 0.4 + stretch * 0.2 + abs(momentum) * 1.5
                reason = f"Extreme continuation up at {price:.4f} (mom={momentum:+.4f})"
            elif momentum < -self.cfg.min_momentum:
                direction = "BUY_NO"
                stretch = (price - 0.5) * 2.0
                confidence = 0.4 + stretch * 0.2 + abs(momentum) * 1.5
                reason = f"Extreme continuation down at {price:.4f} (mom={momentum:+.4f})"

        elif price_zone in ("fair", "discount", "premium"):
            ob_imbalance = market_state.get("orderbook_imbalance", 0) or 0
            vol_change = market_state.get("volume_5m", 0) or 0
            if abs(ob_imbalance) > self.cfg.mid_zone_orderbook_threshold and vol_change > self.cfg.min_volume_5m * 2:
                if ob_imbalance > 0:
                    direction = "BUY_YES"
                    confidence = 0.3 + abs(ob_imbalance) * 0.3
                    reason = f"Mid-zone orderbook imbalance at {price:.4f} (ob={ob_imbalance:+.3f})"
                else:
                    direction = "BUY_NO"
                    confidence = 0.3 + abs(ob_imbalance) * 0.3
                    reason = f"Mid-zone orderbook imbalance at {price:.4f} (ob={ob_imbalance:+.3f})"

        if direction is None:
            return None

        if volatility is not None and volatility > self.cfg.high_volatility_threshold:
            confidence *= 0.6

        resolution_bucket = market_state.get("resolution_bucket")
        if resolution_bucket == "last_hour":
            confidence *= 0.5
        elif resolution_bucket == "last_day":
            confidence *= 0.8

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
            market_regime=regime,
            strategy_version=self.version,
            feature_values={
                "current_price": price,
                "price_zone": price_zone,
                "momentum_1h": round(momentum, 4),
                "spread_ratio": round(spread_ratio, 4),
                "volatility_1h": volatility,
                "orderbook_imbalance": market_state.get("orderbook_imbalance"),
                "regime": regime,
                "archetype": market_state.get("archetype"),
                "resolution_bucket": resolution_bucket,
                "hours_to_resolution": market_state.get("hours_to_resolution"),
            },
        )
