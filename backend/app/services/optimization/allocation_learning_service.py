from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import AllocationLearningUpdate, AllocationLearningOutput
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


class AllocationLearningService(SafeRedisMixin):
    LEARN_PREFIX = "optimization:learning"

    def __init__(self):
        self._local_outputs: list[AllocationLearningOutput] = []

    async def update(
        self,
        current_weights: dict[str, float],
        expected_returns: dict[str, float],
        actual_returns: dict[str, float] | None = None,
        regime_accuracy: dict[str, float] | None = None,
        stress_survivability: dict[str, float] | None = None,
        tier_caps: dict[str, float] | None = None,
        learning_rate: float = 0.1,
        seed: int | None = None,
    ) -> AllocationLearningOutput:
        caps = tier_caps or {}
        actual = actual_returns or {}
        regime_acc = regime_accuracy or {}
        stress = stress_survivability or {}

        updates: list[AllocationLearningUpdate] = []
        risk_penalty_update: dict[str, float] = {}
        adjusted = dict(current_weights)

        for sid, w in current_weights.items():
            expected = expected_returns.get(sid, 0.0)
            actual_r = actual.get(sid, expected)
            perf_delta = actual_r - expected

            signal = learning_rate * perf_delta
            new_w = w * (1.0 + signal)

            reason_parts = []
            if abs(perf_delta) > 0.001:
                direction = "outperformed" if perf_delta > 0 else "underperformed"
                reason_parts.append(f"{direction} expectations by {abs(perf_delta):.4f}")
            if sid in stress and stress[sid] < 30:
                risk_penalty_update[sid] = round(stress[sid] / 100.0, 4)
                reason_parts.append(f"low stress survivability ({stress[sid]:.1f})")
                new_w *= 0.8

            cap = caps.get(sid, 100.0) / 100.0
            new_w = max(0.0, min(cap, new_w))

            adjusted[sid] = new_w

            updates.append(AllocationLearningUpdate(
                strategy_id=sid,
                previous_weight=round(w, 4),
                adjusted_weight=round(new_w, 4),
                adjustment_reason="; ".join(reason_parts) if reason_parts else "no significant signal",
                learning_signal=round(signal, 6),
                performance_delta=round(perf_delta, 6),
            ))

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        for sid in adjusted:
            cap = caps.get(sid, 100.0) / 100.0
            adjusted[sid] = min(cap, adjusted[sid])

        regime_calibration: dict[str, float] = {}
        for regime, acc in regime_acc.items():
            calibrated = min(1.0, max(0.1, acc))
            regime_calibration[regime] = round(calibrated, 4)

        for sid in adjusted:
            if sid not in risk_penalty_update:
                risk_penalty_update[sid] = 0.0

        output = AllocationLearningOutput(
            updates=updates,
            regime_calibration=regime_calibration,
            risk_penalty_update=risk_penalty_update,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_outputs.append(output)
        await self._safe_redis("rpush", self.LEARN_PREFIX, output.model_dump_json())
        await audit_emit("allocation.learned", "optimization", "learning", {
            "strategies": len(updates), "regime_calibration": len(regime_calibration),
        })
        return output

    async def get_latest(self) -> AllocationLearningOutput | None:
        raw = await self._safe_redis("lrange", self.LEARN_PREFIX, -1, -1)
        if raw:
            try:
                return AllocationLearningOutput.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_outputs[-1] if self._local_outputs else None

    async def get_all(self) -> list[AllocationLearningOutput]:
        raw = await self._safe_redis("lrange", self.LEARN_PREFIX, 0, -1)
        if raw:
            try:
                return [AllocationLearningOutput.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_outputs)


allocation_learning_service = AllocationLearningService()
