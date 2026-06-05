import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import PortfolioReviewReport
from app.services.intelligence.portfolio_intelligence_service import portfolio_intelligence_service
from app.services.intelligence.regime_allocation_service import regime_allocation_service
from app.services.intelligence.stress_testing_service import stress_testing_service
from app.services.intelligence.resilience_service import resilience_service
from app.services.intelligence.investment_committee_service import investment_committee_service
from app.services.research.research_memory import research_memory
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


class AutonomousPortfolioReview(SafeRedisMixin):
    REVIEW_PREFIX = "intelligence:reviews"

    def __init__(self):
        self._local_reviews: list[PortfolioReviewReport] = []

    async def run(
        self,
        market_data: dict | None = None,
        tournament_rankings: list[dict] | None = None,
        allocation_plans: list[dict] | None = None,
        strategy_health: list[dict] | None = None,
        strategy_performance: list[dict] | None = None,
        candidate_recommendations: list[dict] | None = None,
        regime_data: dict | None = None,
        strategy_correlations: dict[str, dict[str, float]] | None = None,
        regime_exposure: dict[str, float] | None = None,
        tier_caps: dict[str, float] | None = None,
        strategy_archetypes: dict[str, str] | None = None,
        seed: int | None = None,
    ) -> PortfolioReviewReport:
        await audit_emit("portfolio.review.started", "intelligence", "review", {})

        try:
            from app.services.control.control_plane import control_plane
            state = await control_plane.get_state()
            if not state.get("trading_enabled", True):
                await audit_emit("portfolio.review.skipped", "intelligence", "review", {"reason": "disabled"})
                review = PortfolioReviewReport(
                    review_id=f"pr-{str(uuid.uuid4())[:8]}",
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    summary="Review skipped: trading disabled",
                )
                self._local_reviews.append(review)
                await self._safe_redis("rpush", self.REVIEW_PREFIX, review.model_dump_json())
                return review
        except Exception:
            pass

        intelligence = await portfolio_intelligence_service.compute(
            tournament_rankings=tournament_rankings,
            allocation_plans=allocation_plans,
            strategy_health=strategy_health,
            strategy_performance=strategy_performance,
            regime_data=regime_data,
        )

        regime = regime_data.get("regime", "unknown") if regime_data else "unknown"
        regime_confidence = regime_data.get("confidence", 0.5) if regime_data else 0.5
        current_allocations = [
            {"strategy_id": a.get("strategy_id"), "allocation": a.get("allocation", 0)}
            for a in (allocation_plans or [])
        ]
        regime_plan = await regime_allocation_service.generate(
            regime=regime,
            regime_confidence=regime_confidence,
            current_allocations=current_allocations,
            tier_caps=tier_caps,
            strategy_archetypes=strategy_archetypes,
            seed=seed,
        )

        stress_results = await stress_testing_service.run_all_scenarios(
            strategy_health=strategy_health,
            allocations=allocation_plans,
            seed=seed,
        )

        resilience = await resilience_service.compute(
            allocations=allocation_plans,
            strategy_health=strategy_health,
            strategy_correlations=strategy_correlations,
            regime_exposure=regime_exposure,
        )

        committee = await investment_committee_service.generate(
            intelligence=intelligence,
            resilience=resilience,
            regime_plan=regime_plan,
            stress_results=stress_results,
            strategy_performance=strategy_performance,
            candidate_recommendations=candidate_recommendations,
            seed=seed,
        )

        review = PortfolioReviewReport(
            review_id=f"pr-{str(uuid.uuid4())[:8]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            intelligence=intelligence,
            regime_allocation=regime_plan,
            stress_tests=stress_results,
            resilience=resilience,
            committee=committee,
            summary=f"Review complete: quality={intelligence.quality_score:.1f}, resilience={resilience.survivability_score:.1f}, recommendations={len(committee.recommendations)}",
        )

        self._local_reviews.append(review)
        await self._safe_redis("rpush", self.REVIEW_PREFIX, review.model_dump_json())
        await audit_emit("portfolio.review.generated", "intelligence", "review", {
            "review_id": review.review_id,
            "quality_score": intelligence.quality_score,
            "survivability_score": resilience.survivability_score,
            "recommendations": len(committee.recommendations),
        })
        return review

    async def get_reviews(self) -> list[PortfolioReviewReport]:
        raw = await self._safe_redis("lrange", self.REVIEW_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioReviewReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reviews)

    async def get_latest(self) -> PortfolioReviewReport | None:
        reviews = await self.get_reviews()
        return reviews[-1] if reviews else None


autonomous_portfolio_review = AutonomousPortfolioReview()
