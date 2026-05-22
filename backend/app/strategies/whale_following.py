from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class WhaleFollowingConfig(StrategyConfig):
    min_trade_size: float = Field(default=500, ge=0)
    max_trade_size: float = Field(default=1_000_000, ge=0)
    min_whale_win_rate: float = Field(default=0.55, ge=0, le=1.0)
    recency_bias_hours: int = Field(default=48, ge=1)


class WhaleFollowingStrategy(BaseStrategy):
    name = "whale_following"
    version = "1.0.0"
    description = "Follows large trades from historically profitable wallets"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = WhaleFollowingConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        wallet = market_state.get("wallet", "")
        size = float(market_state.get("size", 0) or 0)
        side = market_state.get("side", "buy")
        wallet_score = market_state.get("wallet_score")

        if not self.cfg.min_trade_size <= size <= self.cfg.max_trade_size:
            return None

        if wallet_score and wallet_score < self.cfg.min_whale_win_rate:
            return None

        direction = "BUY_YES" if side in ("buy", "YES") else "BUY_NO"
        size_ratio = min(size / 10_000, 1.0)
        confidence = 0.5 + (size_ratio * 0.3)
        if wallet_score:
            confidence += (wallet_score - 0.5) * 0.2
        confidence = max(0.1, min(0.95, confidence))

        wr_str = f"{wallet_score:.2f}" if wallet_score is not None else "N/A"

        return StructuredSignal(
            strategy=self.name,
            signal=direction,
            confidence=round(confidence, 4),
            market_condition_id=market_state.get("condition_id") or market_state.get("market_condition_id"),
            market_id=market_state.get("market_id"),
            reason=f"Whale {wallet[:8]} traded {size:.0f} {side.upper()} (win_rate={wr_str})",
            risk_score=round(1.0 - confidence, 4),
            time_horizon="short",
            market_regime="normal",
            strategy_version=self.version,
            feature_values={
                "trade_size": size,
                "wallet_score": wallet_score,
                "size_ratio": round(size_ratio, 4),
                "recency_hours": market_state.get("recency_hours"),
            },
        )
