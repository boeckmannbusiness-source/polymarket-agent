import math
from datetime import datetime, timezone
from typing import Any

from app.schemas.control import DampenedLearningSignal, FeedbackDampeningReport
from app.services.audit.audit_logger import emit as audit_emit


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


class FeedbackDampeningService(SafeRedisMixin):
    PREFIX = "control:dampening"

    def __init__(self):
        self._local_reports: list[FeedbackDampeningReport] = []

    async def dampen(
        self,
        learning_signals: dict[str, float],
        base_learning_rate: float = 0.1,
        volatility_estimate: float = 0.0,
        regime_instability: float = 0.0,
        allocation_variance: float = 0.0,
        min_stability_factor: float = 0.1,
    ) -> FeedbackDampeningReport:
        stability_factor = self._compute_stability_factor(
            volatility_estimate, regime_instability, allocation_variance,
        )
        stability_factor = max(min_stability_factor, stability_factor)

        dampened: list[DampenedLearningSignal] = []
        for sid, signal in learning_signals.items():
            effective_lr = base_learning_rate * stability_factor
            dampened_signal = signal * stability_factor
            dampened.append(DampenedLearningSignal(
                strategy_id=sid,
                raw_signal=round(signal, 6),
                dampened_signal=round(dampened_signal, 6),
                stability_factor=round(stability_factor, 4),
                effective_learning_rate=round(effective_lr, 6),
                volatility=round(volatility_estimate, 6),
            ))

        report = FeedbackDampeningReport(
            dampened_signals=dampened,
            base_learning_rate=base_learning_rate,
            global_stability_factor=round(stability_factor, 4),
            regime_instability=round(regime_instability, 4),
            allocation_variance=round(allocation_variance, 6),
            applied_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.PREFIX, report.model_dump_json())
        await audit_emit("control.feedback.dampened", "control", "dampening", {
            "strategies": len(dampened), "stability_factor": stability_factor,
        })
        return report

    def _compute_stability_factor(
        self, volatility: float, regime_instability: float, allocation_variance: float,
    ) -> float:
        vol_penalty = min(1.0, volatility * 5.0)
        regime_penalty = min(1.0, regime_instability * 2.0)
        variance_penalty = min(1.0, allocation_variance * 50.0)
        factor = 1.0 - 0.4 * vol_penalty - 0.3 * regime_penalty - 0.3 * variance_penalty
        return max(0.1, factor)

    async def get_latest(self) -> FeedbackDampeningReport | None:
        raw = await self._safe_redis("lrange", self.PREFIX, -1, -1)
        if raw:
            try:
                return FeedbackDampeningReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None


feedback_dampening_service = FeedbackDampeningService()
