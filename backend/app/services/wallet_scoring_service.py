import math
from datetime import datetime, timezone
from typing import Any

from app.services.time_decay import TimeDecayService


class WalletScoringService:
    def __init__(self, decay_service: TimeDecayService | None = None):
        self.decay = decay_service or TimeDecayService()

    def compute_score(self, metrics: dict[str, Any]) -> dict[str, Any]:
        trades_1h = metrics.get("trades_1h", 0) or 0
        trades_24h = metrics.get("trades_24h", 0) or 0
        token_diversity = metrics.get("token_diversity", 0) or 0
        volume_proxy = metrics.get("volume_proxy", 0.0) or 0.0
        active_days_7d = metrics.get("active_days_7d", 0) or 0

        hours_since_last_trade = 0.0
        last_trade_raw = metrics.get("last_trade_at")
        if last_trade_raw:
            if isinstance(last_trade_raw, str):
                last_trade = datetime.fromisoformat(last_trade_raw)
            else:
                last_trade = last_trade_raw
            if last_trade.tzinfo is None:
                last_trade = last_trade.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - last_trade
            hours_since_last_trade = max(0.0, delta.total_seconds() / 3600)

        score_1h = self._compute_raw_score(trades_1h, token_diversity, volume_proxy, active_days_7d, hours_since_last_trade)
        score_24h = self._compute_raw_score(trades_24h, token_diversity, volume_proxy, active_days_7d, hours_since_last_trade)

        temporal_stability = 1.0 - abs(score_1h - score_24h)
        temporal_stability = max(0.0, min(1.0, temporal_stability))
        sufficiency = min(trades_24h / 20.0, 1.0)
        confidence = 0.6 * sufficiency + 0.4 * temporal_stability

        classification = self._classify(score_24h, volume_proxy, confidence)

        return {
            "wallet_address": metrics.get("wallet_address", ""),
            "score": round(score_24h, 6),
            "confidence": round(min(confidence, 1.0), 6),
            "classification": classification,
            "score_1h": round(score_1h, 6),
            "score_24h": round(score_24h, 6),
        }

    def _compute_raw_score(self, trades: int, diversity: int, volume: float, active_days: int, hours_since_last_trade: float) -> float:
        freq_component = 0.30 * self.decay.decay_frequency(trades)
        div_norm = min(diversity / 10.0, 1.0)
        div_component = 0.20 * div_norm
        recent = self.decay.decay_recency(hours_since_last_trade)
        recent_component = 0.25 * recent
        vol_norm = min(math.log10(max(volume, 0) + 1) / math.log10(100001), 1.0)
        vol_component = 0.15 * vol_norm
        cons_component = 0.10 * (active_days / 7.0)

        return freq_component + div_component + recent_component + vol_component + cons_component

    def _classify(self, score: float, volume: float, confidence: float) -> str:
        if confidence < 0.30:
            return "unknown"
        if score >= 0.75 and volume >= 50000:
            return "whale"
        if score >= 0.55:
            return "momentum"
        return "retail"

    def compute_scores_batch(self, metrics_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.compute_score(m) for m in metrics_list]
