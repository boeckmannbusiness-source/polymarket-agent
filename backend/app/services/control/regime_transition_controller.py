import math
import random
from datetime import datetime, timezone
from typing import Any

from app.schemas.control import StableRegimeState, RegimeTransitionControlReport
from app.services.audit.audit_logger import emit as audit_emit


TRANSITION_MATRIX: dict[str, dict[str, float]] = {
    "trending": {"trending": 0.70, "mean_reverting": 0.15, "high_volatility": 0.10, "event_driven": 0.05},
    "mean_reverting": {"mean_reverting": 0.65, "trending": 0.20, "low_volatility": 0.10, "high_volatility": 0.05},
    "high_volatility": {"high_volatility": 0.60, "mean_reverting": 0.20, "event_driven": 0.15, "illiquid": 0.05},
    "low_volatility": {"low_volatility": 0.70, "trending": 0.15, "high_volatility": 0.10, "illiquid": 0.05},
    "event_driven": {"event_driven": 0.55, "high_volatility": 0.25, "trending": 0.10, "news_driven": 0.10},
    "news_driven": {"news_driven": 0.60, "high_volatility": 0.20, "mean_reverting": 0.10, "event_driven": 0.10},
    "illiquid": {"illiquid": 0.65, "low_volatility": 0.20, "high_volatility": 0.10, "mean_reverting": 0.05},
}


class SafeRedisMixin:
    async def _safe_redis(self, method: str, *args, **kwargs) -> Any:
        try:
            from app.services.redis import redis_service
            redis = await redis_service.get_client() if hasattr(redis_service, 'get_client') else redis_service.redis
            if redis is None:
                return None
            func = getattr(redis, method, None)
            if func is None:
                return None
            if hasattr(func, '__call__'):
                return await func(*args, **kwargs)
            return None
        except Exception:
            return None


class RegimeTransitionController(SafeRedisMixin):
    PREFIX = "control:regime"

    def __init__(self):
        self._local_reports: list[RegimeTransitionControlReport] = []
        self._persistence_count: dict[str, int] = {}

    async def stabilize(
        self,
        current_regime: str = "",
        regime_probabilities: dict[str, float] | None = None,
        predicted_next_probs: dict[str, float] | None = None,
        volatility_shock: float = 0.0,
        signal_divergence_detected: bool = False,
        inertia_base: float = 0.8,
    ) -> RegimeTransitionControlReport:
        probs = regime_probabilities or {}
        pred = predicted_next_probs or {}

        transition_matrix = self._adjust_transitions(volatility_shock)

        smoothed: list[StableRegimeState] = []
        for regime in sorted(set(list(probs.keys()) + list(TRANSITION_MATRIX.keys()))):
            raw_prob = probs.get(regime, 0.0)
            pred_prob = pred.get(regime, 0.0)

            if current_regime == regime:
                self._persistence_count[regime] = self._persistence_count.get(regime, 0) + 1
            else:
                self._persistence_count[regime] = 0

            persistence = self._persistence_count.get(regime, 0)
            inertia = self._compute_inertia(regime, current_regime, inertia_base, volatility_shock, signal_divergence_detected)

            smoothed_prob = inertia * raw_prob + (1.0 - inertia) * pred_prob
            smoothed_prob = max(0.0, min(1.0, smoothed_prob))

            smoothed.append(StableRegimeState(
                regime=regime,
                probability=round(smoothed_prob, 4),
                persistence_count=persistence,
                inertia=round(inertia, 4),
                transitions_smoothed=True,
            ))

        total = sum(s.probability for s in smoothed)
        if total > 0:
            for s in smoothed:
                s.probability = round(s.probability / total, 4)

        report = RegimeTransitionControlReport(
            regimes=smoothed,
            transition_matrix=transition_matrix,
            volatility_adjustment=round(1.0 + volatility_shock, 4),
            applied_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.PREFIX, report.model_dump_json())
        await audit_emit("control.regime.stabilized", "control", "regime", {
            "regimes": len(smoothed), "current_regime": current_regime,
        })
        return report

    def _compute_inertia(
        self, regime: str, current_regime: str, base: float,
        volatility_shock: float, signal_divergence: bool,
    ) -> float:
        if regime == current_regime:
            persistence_bonus = min(0.15, self._persistence_count.get(regime, 0) * 0.02)
            inertia = base + persistence_bonus
        else:
            inertia = 1.0 - base
        if volatility_shock > 0.5:
            inertia *= 0.7
        if signal_divergence:
            inertia *= 0.8
        return max(0.1, min(0.99, inertia))

    def _adjust_transitions(self, volatility_shock: float) -> dict[str, dict[str, float]]:
        adjusted: dict[str, dict[str, float]] = {}
        for regime, transitions in TRANSITION_MATRIX.items():
            adj = dict(transitions)
            if volatility_shock > 0.3:
                shock = volatility_shock * 0.2
                for target in list(adj.keys()):
                    if target in ("high_volatility", "event_driven"):
                        adj[target] = min(1.0, adj[target] + shock)
                    else:
                        adj[target] = max(0.0, adj[target] - shock * 0.5)
                total = sum(adj.values())
                if total > 0:
                    adj = {k: v / total for k, v in adj.items()}
            adjusted[regime] = {k: round(v, 4) for k, v in adj.items()}
        return adjusted

    async def get_latest(self) -> RegimeTransitionControlReport | None:
        raw = await self._safe_redis("lrange", self.PREFIX, -1, -1)
        if raw:
            try:
                return RegimeTransitionControlReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None


regime_transition_controller = RegimeTransitionController()
