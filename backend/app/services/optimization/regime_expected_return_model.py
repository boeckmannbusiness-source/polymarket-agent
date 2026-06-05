from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import RegimeExpectedReturn, RegimeExpectedReturnsOutput
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


class RegimeExpectedReturnModel(SafeRedisMixin):
    RET_PREFIX = "optimization:expected_returns"

    def __init__(self):
        self._local_outputs: list[RegimeExpectedReturnsOutput] = []

    async def compute(
        self,
        regime_probabilities: dict[str, float],
        strategy_performance_by_regime: dict[str, dict[str, float]],
        confidence_weights: dict[str, float] | None = None,
    ) -> RegimeExpectedReturnsOutput:
        conf = confidence_weights or {}
        strategy_ids: set[str] = set()
        for perf in strategy_performance_by_regime.values():
            strategy_ids.update(perf.keys())

        returns_list: list[RegimeExpectedReturn] = []
        for sid in sorted(strategy_ids):
            total_er = 0.0
            regime_contributions: dict[str, float] = {}
            for regime, prob in regime_probabilities.items():
                regime_perf = strategy_performance_by_regime.get(regime, {})
                regime_return = regime_perf.get(sid, 0.0)
                cw = conf.get(regime, 1.0)
                contribution = prob * regime_return * cw
                total_er += contribution
                regime_contributions[regime] = round(contribution, 6)

            overall_confidence = sum(
                regime_probabilities.get(r, 0.0) * conf.get(r, 1.0) for r in regime_probabilities
            ) / max(len(regime_probabilities), 1)

            returns_list.append(RegimeExpectedReturn(
                strategy_id=sid,
                expected_return=round(total_er, 6),
                regime_contributions=regime_contributions,
                confidence=round(min(1.0, overall_confidence), 4),
            ))

        output = RegimeExpectedReturnsOutput(
            returns=returns_list,
            regime_probabilities=regime_probabilities,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_outputs.append(output)
        await self._safe_redis("rpush", self.RET_PREFIX, output.model_dump_json())
        await audit_emit("expected.returns.computed", "optimization", "expected_returns", {
            "strategies": len(returns_list), "regimes": len(regime_probabilities),
        })
        return output

    async def get_latest(self) -> RegimeExpectedReturnsOutput | None:
        raw = await self._safe_redis("lrange", self.RET_PREFIX, -1, -1)
        if raw:
            try:
                return RegimeExpectedReturnsOutput.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_outputs[-1] if self._local_outputs else None

    async def get_all(self) -> list[RegimeExpectedReturnsOutput]:
        raw = await self._safe_redis("lrange", self.RET_PREFIX, 0, -1)
        if raw:
            try:
                return [RegimeExpectedReturnsOutput.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_outputs)


regime_expected_return_model = RegimeExpectedReturnModel()
