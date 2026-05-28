from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal
from pydantic import Field


class EnsembleConfig(StrategyConfig):
    regime_weights: dict = Field(
        default_factory=lambda: {
            "high_volatility": {"momentum_spike": 0.4, "early_whale_entry": 0.3, "whale_following": 0.3},
            "low_volatility": {"spread_compression": 0.4, "liquidity_vacuum": 0.3, "whale_following": 0.3},
            "momentum": {"momentum_spike": 0.5, "news_repricing": 0.3, "whale_following": 0.2},
            "mean_reverting": {"spread_compression": 0.4, "liquidity_vacuum": 0.3, "coordinated_wallets": 0.3},
            "illiquid": {"whale_following": 0.5, "liquidity_vacuum": 0.3, "coordinated_wallets": 0.2},
            "normal": {"whale_following": 0.2, "early_whale_entry": 0.2, "momentum_spike": 0.2,
                       "spread_compression": 0.2, "liquidity_vacuum": 0.2},
        }
    )
    min_ensemble_confidence: float = 0.3
    max_ensemble_signals: int = 10


class EnsembleStrategy(BaseStrategy):
    name = "ensemble"
    version = "1.0.0"
    description = "Meta-strategy that weights sub-strategies by detected market regime"

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.cfg = EnsembleConfig(**(config or {}))

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        regime = market_state.get("regime", "normal")
        weights = self.cfg.regime_weights.get(regime, self.cfg.regime_weights.get("normal", {}))

        if not weights:
            return None

        from app.strategies import get_strategy

        weighted_signals = []
        for strategy_name, weight in weights.items():
            try:
                strategy = get_strategy(strategy_name)
                if not strategy.config.enabled:
                    continue
                signal = await strategy.generate_signal(market_state)
                if signal is not None:
                    weighted_signals.append((weight, signal))
            except Exception:
                continue

        if not weighted_signals:
            return None

        total_weight = sum(w for w, _ in weighted_signals)
        if total_weight == 0:
            return None

        weighted_signals.sort(key=lambda x: x[1].confidence * x[0], reverse=True)
        best_weight, best_signal = weighted_signals[0]

        avg_confidence = sum(s.confidence * w for w, s in weighted_signals) / total_weight
        if avg_confidence < self.cfg.min_ensemble_confidence:
            return None

        regime_scores = {s.strategy: round(w / total_weight, 4) for w, s in weighted_signals}
        tally = {"BUY_YES": 0.0, "BUY_NO": 0.0, "NEUTRAL": 0.0}
        for w, s in weighted_signals:
            tally[s.signal] = tally.get(s.signal, 0) + w
        consensus_signal = max(tally, key=tally.get)

        all_reasons = [s.reason for _, s in weighted_signals]

        return StructuredSignal(
            strategy=self.name,
            signal=consensus_signal,
            confidence=round(avg_confidence, 4),
            market_id=market_state.get("market_id"),
            market_condition_id=market_state.get("condition_id"),
            reason=f"Ensemble({regime}): {'; '.join(all_reasons[:3])}",
            risk_score=round(1.0 - avg_confidence, 4),
            time_horizon="medium",
            market_regime=regime,
            strategy_version=self.version,
            feature_values={
                **market_state,
                "ensemble_regime": regime,
                "ensemble_weights": regime_scores,
                "ensemble_contributors": [s.strategy for _, s in weighted_signals],
            },
        )

    def get_metadata(self) -> dict:
        meta = super().get_metadata()
        meta["ensemble_regime_weights"] = self.cfg.regime_weights
        return meta
