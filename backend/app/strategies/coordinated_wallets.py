from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class CoordinatedWalletsConfig(StrategyConfig):
    min_trade_size: float = Field(default=200, ge=0)
    max_trade_size: float = Field(default=10000, ge=0)
    min_wallet_score: float = Field(default=0.3, ge=0, le=1.0)
    max_wallet_score: float = Field(default=0.8, ge=0, le=1.0)


class CoordinatedWalletsStrategy(BaseStrategy):
    name = "coordinated_wallets"
    version = "1.0.0"
    description = "Detects clusters of wallets acting in coordination on the same markets"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = CoordinatedWalletsConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        size = float(market_state.get("size", 0) or 0)
        if not (self.cfg.min_trade_size <= size <= self.cfg.max_trade_size):
            return None

        wallet = market_state.get("wallet", "")
        wallet_score = market_state.get("wallet_score")
        side = market_state.get("side", "buy")
        outcome = market_state.get("outcome", "YES")

        if wallet_score is not None:
            if wallet_score < self.cfg.min_wallet_score or wallet_score > self.cfg.max_wallet_score:
                return None

        current_price = market_state.get("current_price")
        if current_price is None or current_price <= 0:
            return None

        direction = "BUY_YES" if side.upper() in ("BUY", "YES") else "BUY_NO"
        size_confidence = min(size / 2000, 1.0) * 0.3
        score_confidence = (wallet_score - 0.3) * 0.4 if wallet_score else 0.2
        confidence = 0.3 + size_confidence + score_confidence
        confidence = max(0.1, min(0.9, confidence))

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            reason=f"Coordinated pattern: wallet {wallet[:8]} traded {size:.0f} {outcome} (score={wallet_score:.2f})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="medium",
            market_regime=market_state.get("regime", "normal"),
            strategy_version=self.version,
            feature_values={
                "trade_size": size,
                "wallet_score": wallet_score,
                "wallet_prefix": wallet[:8] if wallet else None,
                "outcome": outcome,
            },
        )
