import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import InvestmentCommitteeReport, CommitteeRecommendation, PortfolioIntelligenceReport
from app.schemas.intelligence import ResilienceReport, RegimeAllocationPlan, StressTestResult
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


class InvestmentCommitteeService(SafeRedisMixin):
    COMM_PREFIX = "intelligence:committee"

    def __init__(self):
        self._local_reports: list[InvestmentCommitteeReport] = []

    async def generate(
        self,
        intelligence: PortfolioIntelligenceReport | None = None,
        resilience: ResilienceReport | None = None,
        regime_plan: RegimeAllocationPlan | None = None,
        stress_results: list[StressTestResult] | None = None,
        strategy_performance: list[dict] | None = None,
        candidate_recommendations: list[dict] | None = None,
        seed: int | None = None,
    ) -> InvestmentCommitteeReport:
        import random
        rng = random.Random(seed) if seed is not None else random.Random()

        recommendations: list[CommitteeRecommendation] = []

        intel_recos = self._generate_intel_recommendations(intelligence, strategy_performance)
        recommendations.extend(intel_recos)

        stress_recos = self._generate_stress_recommendations(stress_results or [])
        recommendations.extend(stress_recos)

        res_recos = self._generate_resilience_recommendations(resilience)
        recommendations.extend(res_recos)

        candidate_recos = self._generate_candidate_recommendations(candidate_recommendations or [])
        recommendations.extend(candidate_recos)

        regime_recos = self._generate_regime_recommendations(regime_plan)
        recommendations.extend(regime_recos)

        if not recommendations:
            recommendations.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale="No specific recommendations at this time. Continuing observation.",
                supporting_metrics={"intelligence_quality": intelligence.quality_score if intelligence else 0},
                confidence=0.3,
            ))

        n_recos = len(recommendations)
        summary_lines = [f"Generated {n_recos} recommendation{'s' if n_recos != 1 else ''}"]
        high_conf = [r for r in recommendations if r.confidence >= 0.7]
        if high_conf:
            summary_lines.append(f"{len(high_conf)} high-confidence recommendation{'s' if len(high_conf) != 1 else ''}")
        summary = ". ".join(summary_lines)

        report = InvestmentCommitteeReport(
            report_id=f"ic-{str(uuid.uuid4())[:8]}",
            recommendations=recommendations,
            summary=summary,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.COMM_PREFIX, report.model_dump_json())
        await audit_emit("committee.report.generated", "intelligence", "committee", {
            "report_id": report.report_id,
            "recommendations": n_recos,
        })
        return report

    def _generate_intel_recommendations(self, intelligence: PortfolioIntelligenceReport | None, perf: list[dict] | None) -> list[CommitteeRecommendation]:
        recos: list[CommitteeRecommendation] = []
        if not intelligence:
            return recos
        if intelligence.quality_score < 50:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale="Portfolio quality score is low. Consider reducing concentration and improving diversification.",
                supporting_metrics={"quality_score": intelligence.quality_score, "diversification": intelligence.diversification_score},
                confidence=0.6,
            ))
        if intelligence.concentration_score > 60:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale=f"High concentration risk (score: {intelligence.concentration_score}). Consider rebalancing.",
                supporting_metrics={"concentration_score": intelligence.concentration_score},
                confidence=0.7,
            ))
        if intelligence.diversification_score < 30:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale="Portfolio is poorly diversified. Consider adding strategies with different archetypes.",
                supporting_metrics={"diversification_score": intelligence.diversification_score},
                confidence=0.65,
            ))
        if perf:
            top = max(perf, key=lambda p: p.get("sharpe", 0)) if perf else None
            if top and top.get("sharpe", 0) > 1.5:
                recos.append(CommitteeRecommendation(
                    recommendation_type="increase_allocation",
                    target=top.get("strategy_id", top.get("strategy", "unknown")),
                    rationale=f"Top performer with Sharpe {top.get('sharpe', 0):.2f}. Consider increasing allocation.",
                    supporting_metrics={"sharpe": top.get("sharpe", 0)},
                    confidence=0.5,
                ))
            worst = min(perf, key=lambda p: p.get("sharpe", 0)) if perf and len(perf) > 1 else None
            if worst and worst.get("sharpe", 0) < -0.5:
                recos.append(CommitteeRecommendation(
                    recommendation_type="retire_strategy",
                    target=worst.get("strategy_id", worst.get("strategy", "unknown")),
                    rationale=f"Underperformer with negative Sharpe {worst.get('sharpe', 0):.2f}. Consider retirement.",
                    supporting_metrics={"sharpe": worst.get("sharpe", 0)},
                    confidence=0.55,
                ))
        return recos

    def _generate_stress_recommendations(self, stress_results: list[StressTestResult]) -> list[CommitteeRecommendation]:
        recos: list[CommitteeRecommendation] = []
        for sr in stress_results:
            if sr.expected_drawdown > 0.3:
                recos.append(CommitteeRecommendation(
                    recommendation_type="reduce_concentration",
                    target=f"stress:{sr.scenario_type}",
                    rationale=f"Stress test '{sr.scenario_type}' shows {sr.expected_drawdown:.1%} expected drawdown. Strengthen hedging.",
                    supporting_metrics={"expected_drawdown": sr.expected_drawdown, "resilience_score": sr.resilience_score},
                    confidence=0.6,
                ))
            low_survivors = [sid for sid, surv in sr.strategy_survivability.items() if surv < 30]
            for sid in low_survivors[:2]:
                recos.append(CommitteeRecommendation(
                    recommendation_type="retire_strategy",
                    target=sid,
                    rationale=f"Low survivability ({sr.strategy_survivability[sid]:.1f}) under '{sr.scenario_type}' stress scenario.",
                    supporting_metrics={"survivability": sr.strategy_survivability[sid], "scenario": sr.scenario_type},
                    confidence=0.5,
                ))
        return recos

    def _generate_resilience_recommendations(self, resilience: ResilienceReport | None) -> list[CommitteeRecommendation]:
        recos: list[CommitteeRecommendation] = []
        if not resilience:
            return recos
        if resilience.concentration_risk > 50:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale=f"High concentration risk ({resilience.concentration_risk:.1f}). Diversify across more strategies.",
                supporting_metrics={"concentration_risk": resilience.concentration_risk},
                confidence=0.7,
            ))
        if resilience.single_strategy_exposure > 30:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale=f"Single strategy exposure at {resilience.single_strategy_exposure:.1f}%. Cap individual strategy allocation.",
                supporting_metrics={"single_strategy_exposure": resilience.single_strategy_exposure},
                confidence=0.75,
            ))
        if resilience.dependency_risk > 60:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale=f"High dependency risk ({resilience.dependency_risk:.1f}). Strategies are too correlated.",
                supporting_metrics={"dependency_risk": resilience.dependency_risk},
                confidence=0.6,
            ))
        if resilience.survivability_score < 40:
            recos.append(CommitteeRecommendation(
                recommendation_type="reduce_concentration",
                target="portfolio",
                rationale=f"Low portfolio survivability ({resilience.survivability_score:.1f}). Consider risk reduction.",
                supporting_metrics={"survivability_score": resilience.survivability_score},
                confidence=0.8,
            ))
        return recos

    def _generate_candidate_recommendations(self, candidates: list[dict]) -> list[CommitteeRecommendation]:
        recos: list[CommitteeRecommendation] = []
        for c in candidates:
            if c.get("incubation_ready") and c.get("confidence", 0) >= 0.4:
                recos.append(CommitteeRecommendation(
                    recommendation_type="incubate_candidate",
                    target=c.get("candidate_id", c.get("strategy_id", "unknown")),
                    rationale=f"Candidate ready for incubation with confidence {c.get('confidence', 0):.2f}.",
                    supporting_metrics={"confidence": c.get("confidence", 0), "novelty": c.get("novelty_score", 0)},
                    confidence=min(0.8, c.get("confidence", 0) + 0.2),
                ))
        return recos

    def _generate_regime_recommendations(self, plan: RegimeAllocationPlan | None) -> list[CommitteeRecommendation]:
        recos: list[CommitteeRecommendation] = []
        if not plan:
            return recos
        high_conf_adj = [a for a in plan.adjustments if a.confidence >= 0.7 and a.delta > 0]
        for adj in high_conf_adj[:2]:
            recos.append(CommitteeRecommendation(
                recommendation_type="increase_allocation",
                target=adj.strategy_id,
                rationale=adj.rationale,
                supporting_metrics={"delta": adj.delta, "confidence": adj.confidence},
                confidence=adj.confidence,
            ))
        return recos

    async def get_latest(self) -> InvestmentCommitteeReport | None:
        raw = await self._safe_redis("lrange", self.COMM_PREFIX, -1, -1)
        if raw:
            try:
                return InvestmentCommitteeReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None

    async def get_all(self) -> list[InvestmentCommitteeReport]:
        raw = await self._safe_redis("lrange", self.COMM_PREFIX, 0, -1)
        if raw:
            try:
                return [InvestmentCommitteeReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)


investment_committee_service = InvestmentCommitteeService()
