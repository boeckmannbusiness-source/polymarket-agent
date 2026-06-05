from datetime import datetime, timezone
from typing import Any

from app.schemas.control import StrategyStableAllocation, StabilityAdjustmentReport
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


class StabilityController(SafeRedisMixin):
    PREFIX = "control:stability"

    def __init__(self):
        self._local_reports: list[StabilityAdjustmentReport] = []

    async def apply_stability_constraints(
        self,
        current_weights: dict[str, float],
        previous_weights: dict[str, float] | None = None,
        regime_probabilities: dict[str, float] | None = None,
        previous_regime_probabilities: dict[str, float] | None = None,
        risk_penalties: dict[str, float] | None = None,
        max_delta_weight: float = 0.05,
        total_turnover_cap: float = 0.20,
        ema_smoothing_factor: float = 0.3,
    ) -> StabilityAdjustmentReport:
        prev_w = previous_weights or {}
        alpha = ema_smoothing_factor
        allocations: list[StrategyStableAllocation] = []
        turnover_sum = 0.0
        stabilized: dict[str, float] = {}

        all_sids = set(current_weights.keys()) | set(prev_w.keys())
        for sid in sorted(all_sids):
            w_new = current_weights.get(sid, 0.0)
            w_prev = prev_w.get(sid, 0.0)
            raw_delta = w_new - w_prev
            capped_delta = max(-max_delta_weight, min(max_delta_weight, raw_delta))
            w_clipped = w_prev + capped_delta
            w_stable = alpha * w_clipped + (1.0 - alpha) * w_prev
            w_stable = max(0.0, w_stable)
            delta = w_stable - w_prev
            turnover_sum += abs(delta)
            allocations.append(StrategyStableAllocation(
                strategy_id=sid,
                raw_weight_pct=round(w_new * 100, 4),
                stabilized_weight_pct=round(w_stable * 100, 4),
                delta_pct=round(delta * 100, 4),
                ema_alpha=round(alpha, 4),
            ))
            stabilized[sid] = w_stable

        total_stable = sum(stabilized.values())
        if total_stable > 0:
            stabilized = {k: v / total_stable for k, v in stabilized.items()}

        reg_stable = self._smooth_probabilities(
            regime_probabilities or {}, previous_regime_probabilities or {}, alpha,
        )
        rp_stable = self._smooth_risk_penalties(risk_penalties or {}, alpha)

        report = StabilityAdjustmentReport(
            max_delta_weight=max_delta_weight,
            total_turnover_pct=round(min(turnover_sum, total_turnover_cap) * 100, 4),
            allocations=allocations,
            regime_probabilities_stabilized=reg_stable,
            risk_penalties_stabilized=rp_stable,
            ema_smoothing_factor=round(alpha, 4),
            applied_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.PREFIX, report.model_dump_json())
        await audit_emit("control.stability.applied", "control", "stability", {
            "allocations": len(allocations), "turnover": report.total_turnover_pct,
        })
        return report

    def _smooth_probabilities(
        self, current: dict[str, float], previous: dict[str, float], alpha: float,
    ) -> dict[str, float]:
        keys = set(current.keys()) | set(previous.keys())
        smoothed = {}
        for k in keys:
            c = current.get(k, 0.0)
            p = previous.get(k, 0.0)
            smoothed[k] = alpha * c + (1.0 - alpha) * p
        total = sum(smoothed.values())
        if total > 0:
            smoothed = {k: v / total for k, v in smoothed.items()}
        return {k: round(v, 4) for k, v in smoothed.items()}

    def _smooth_risk_penalties(self, penalties: dict[str, float], alpha: float) -> dict[str, float]:
        return {k: round(alpha * v + (1.0 - alpha) * v, 4) for k, v in penalties.items()}

    async def get_latest(self) -> StabilityAdjustmentReport | None:
        raw = await self._safe_redis("lrange", self.PREFIX, -1, -1)
        if raw:
            try:
                return StabilityAdjustmentReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None


stability_controller = StabilityController()
