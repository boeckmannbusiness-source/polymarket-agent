import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import PortfolioIntelligenceReport
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


class PortfolioIntelligenceService(SafeRedisMixin):
    INTEL_PREFIX = "intelligence:portfolio"

    def __init__(self):
        self._local_reports: list[PortfolioIntelligenceReport] = []

    async def compute(
        self,
        tournament_rankings: list[dict] | None = None,
        allocation_plans: list[dict] | None = None,
        strategy_health: list[dict] | None = None,
        strategy_performance: list[dict] | None = None,
        regime_data: dict | None = None,
    ) -> PortfolioIntelligenceReport:
        rankings = tournament_rankings or []
        plans = allocation_plans or []
        health = strategy_health or []
        perf = strategy_performance or []

        n_strategies = max(len(rankings), len(plans), len(health), len(perf), 1)

        quality_score = self._compute_quality_score(health, perf, rankings)
        diversification_score = self._compute_diversification(plans)
        concentration_score = self._compute_concentration(plans)
        regime_fitness_score = self._compute_regime_fitness(regime_data, perf)
        strategy_overlap_score = self._compute_strategy_overlap(rankings)
        capital_efficiency_score = self._compute_capital_efficiency(perf, plans)

        report = PortfolioIntelligenceReport(
            quality_score=round(quality_score, 2),
            diversification_score=round(diversification_score, 2),
            concentration_score=round(concentration_score, 2),
            regime_fitness_score=round(regime_fitness_score, 2),
            strategy_overlap_score=round(strategy_overlap_score, 2),
            capital_efficiency_score=round(capital_efficiency_score, 2),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.INTEL_PREFIX, report.model_dump_json())
        await audit_emit("portfolio.intelligence.generated", "intelligence", "portfolio", {
            "quality_score": quality_score,
            "diversification_score": diversification_score,
        })
        return report

    def _compute_quality_score(self, health: list[dict], perf: list[dict], rankings: list[dict]) -> float:
        if not health and not perf and not rankings:
            return 50.0
        scores = []
        for h in health:
            scores.append(h.get("score", 50))
        for p in perf:
            scores.append(max(0, min(100, (p.get("sharpe", 0) * 20 + 50))))
        for r in rankings:
            rank = r.get("rank", 99)
            scores.append(max(0, 100 - rank * 10))
        if not scores:
            return 50.0
        return sum(scores) / len(scores)

    def _compute_diversification(self, plans: list[dict]) -> float:
        if not plans:
            return 100.0
        allocations = [p.get("allocation", 0) for p in plans]
        total = sum(allocations)
        if total == 0:
            return 100.0
        weights = [a / total for a in allocations]
        hhi = sum(w * w for w in weights)
        n = len(weights)
        if n <= 1:
            return 0.0
        min_hhi = 1.0 / n
        if hhi <= min_hhi:
            return 100.0
        return max(0, min(100, (1 - hhi) / (1 - min_hhi) * 100))

    def _compute_concentration(self, plans: list[dict]) -> float:
        if not plans:
            return 0.0
        allocations = [p.get("allocation", 0) for p in plans]
        total = sum(allocations)
        if total == 0:
            return 0.0
        weights = [a / total for a in allocations]
        hhi = sum(w * w for w in weights)
        return round(min(100, hhi * 100), 2)

    def _compute_regime_fitness(self, regime_data: dict | None, perf: list[dict]) -> float:
        if not regime_data:
            return 50.0
        regime = regime_data.get("regime", "unknown")
        if regime == "unknown":
            return 50.0
        score = 50.0
        trending_ok = regime in ("trending", "high_volatility")
        for p in perf:
            sharpe = p.get("sharpe", 0)
            arch = p.get("archetype", "")
            if trending_ok and "momentum" in arch:
                score += 10
            elif regime == "mean_reverting" and "reversion" in arch:
                score += 10
            elif regime == "news_driven" and "sentiment" in arch:
                score += 10
            if sharpe > 0:
                score += 5
        return max(0, min(100, score))

    def _compute_strategy_overlap(self, rankings: list[dict]) -> float:
        if len(rankings) < 2:
            return 100.0
        archetypes = [r.get("archetype", "unknown") for r in rankings]
        unique = len(set(archetypes))
        return round(unique / len(archetypes) * 100, 2)

    def _compute_capital_efficiency(self, perf: list[dict], plans: list[dict]) -> float:
        if not perf or not plans:
            return 50.0
        scores = []
        for p in perf:
            sharpe = p.get("sharpe", 0)
            drawdown = p.get("max_drawdown", 0.5)
            if drawdown <= 0:
                efficiency = 50.0
            else:
                efficiency = max(0, min(100, (sharpe / drawdown) * 10))
            scores.append(efficiency)
        if not scores:
            return 50.0
        return round(sum(scores) / len(scores), 2)

    async def get_latest(self) -> PortfolioIntelligenceReport | None:
        raw = await self._safe_redis("lrange", self.INTEL_PREFIX, -1, -1)
        if raw:
            try:
                return PortfolioIntelligenceReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None

    async def get_all(self) -> list[PortfolioIntelligenceReport]:
        raw = await self._safe_redis("lrange", self.INTEL_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioIntelligenceReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)


portfolio_intelligence_service = PortfolioIntelligenceService()
