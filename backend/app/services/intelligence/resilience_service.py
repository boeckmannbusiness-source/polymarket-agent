from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import ResilienceReport
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


class ResilienceService(SafeRedisMixin):
    RESIL_PREFIX = "intelligence:resilience"

    def __init__(self):
        self._local_reports: list[ResilienceReport] = []

    async def compute(
        self,
        allocations: list[dict] | None = None,
        strategy_health: list[dict] | None = None,
        strategy_correlations: dict[str, dict[str, float]] | None = None,
        regime_exposure: dict[str, float] | None = None,
    ) -> ResilienceReport:
        allocs = allocations or []
        health = strategy_health or []
        correlations = strategy_correlations or {}
        regime_exp = regime_exposure or {}

        concentration_risk = self._compute_concentration_risk(allocs)
        dependency_risk = self._compute_dependency_risk(correlations)
        single_strategy_exposure = self._compute_single_strategy_exposure(allocs)
        single_regime_exposure = self._compute_single_regime_exposure(regime_exp)
        survivability_score = self._compute_survivability(health, concentration_risk, dependency_risk)

        report = ResilienceReport(
            concentration_risk=round(concentration_risk, 2),
            dependency_risk=round(dependency_risk, 2),
            single_strategy_exposure=round(single_strategy_exposure, 2),
            single_regime_exposure=round(single_regime_exposure, 2),
            survivability_score=round(survivability_score, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.RESIL_PREFIX, report.model_dump_json())
        await audit_emit("resilience.report.generated", "intelligence", "resilience", {
            "concentration_risk": concentration_risk,
            "dependency_risk": dependency_risk,
            "survivability_score": survivability_score,
        })
        return report

    def _compute_concentration_risk(self, allocations: list[dict]) -> float:
        if not allocations:
            return 0.0
        allocs = [a.get("allocation", 0) for a in allocations]
        total = sum(allocs)
        if total == 0:
            return 0.0
        weights = [a / total for a in allocs]
        hhi = sum(w * w for w in weights)
        return min(100, hhi * 100)

    def _compute_dependency_risk(self, correlations: dict[str, dict[str, float]]) -> float:
        if not correlations:
            return 0.0
        all_corrs: list[float] = []
        for s1, inner in correlations.items():
            for s2, val in inner.items():
                if s1 != s2:
                    all_corrs.append(abs(val))
        if not all_corrs:
            return 0.0
        avg_corr = sum(all_corrs) / len(all_corrs)
        return min(100, avg_corr * 100)

    def _compute_single_strategy_exposure(self, allocations: list[dict]) -> float:
        if not allocations:
            return 0.0
        max_alloc = max(a.get("allocation", 0) for a in allocations)
        return round(max_alloc, 2)

    def _compute_single_regime_exposure(self, regime_exposure: dict[str, float]) -> float:
        if not regime_exposure:
            return 0.0
        return round(max(regime_exposure.values()), 2)

    def _compute_survivability(self, health: list[dict], concentration_risk: float, dependency_risk: float) -> float:
        if not health:
            return 50.0
        avg_health = sum(h.get("score", 50) for h in health) / len(health)
        penalty = (concentration_risk * 0.3 + dependency_risk * 0.2)
        return max(0, min(100, avg_health * 0.7 - penalty + 30))

    async def get_latest(self) -> ResilienceReport | None:
        raw = await self._safe_redis("lrange", self.RESIL_PREFIX, -1, -1)
        if raw:
            try:
                return ResilienceReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None

    async def get_all(self) -> list[ResilienceReport]:
        raw = await self._safe_redis("lrange", self.RESIL_PREFIX, 0, -1)
        if raw:
            try:
                return [ResilienceReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)


resilience_service = ResilienceService()
