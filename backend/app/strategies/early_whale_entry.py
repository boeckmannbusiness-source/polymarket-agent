from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class EarlyWhaleEntryConfig(StrategyConfig):
    min_trade_size: float = Field(default=200, ge=0)
    max_trade_size: float = Field(default=3000, ge=0)
    min_momentum_5m: float = Field(default=0.005, ge=0)
    max_wallet_score: float = Field(default=0.6, ge=0, le=1.0)


class EarlyWhaleEntryStrategy(BaseStrategy):
    name = "early_whale_entry"
    version = "1.0.0"
    description = "Detects whales entering early positions before significant odds moves"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = EarlyWhaleEntryConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        size = float(market_state.get("size", 0) or 0)
        if not (self.cfg.min_trade_size <= size <= self.cfg.max_trade_size):
            return None

        side = market_state.get("side", "buy")
        momentum = market_state.get("momentum_1h")
        wallet_score = market_state.get("wallet_score")
        current_price = market_state.get("current_price")

        if current_price is None or current_price <= 0:
            return None

        if wallet_score is not None and wallet_score > self.cfg.max_wallet_score:
            return None

        direction = "BUY_YES" if side.upper() in ("BUY", "YES") else "BUY_NO"
        size_confidence = min(size / 1000, 1.0) * 0.2
        base_confidence = 0.4 + size_confidence

        if momentum is not None and abs(momentum) > 0:
            aligned = (momentum > 0 and direction == "BUY_YES") or (momentum < 0 and direction == "BUY_NO")
            if aligned and abs(momentum) >= self.cfg.min_momentum_5m:
                base_confidence += min(abs(momentum) * 2, 0.2)

        confidence = max(0.1, min(0.9, base_confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=f"Early whale entry detected: {size:.0f} {side.upper()} by wallet with score {wallet_score if wallet_score else 'N/A'}",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="medium",
            market_regime=market_state.get("regime", "normal"),
            strategy_version=self.version,
            feature_values={
                "trade_size": size,
                "wallet_score": wallet_score,
                "momentum_1h": round(momentum, 4) if momentum else None,
            },
        )
