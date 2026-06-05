from datetime import datetime, timezone
from typing import Any

from app.schemas.lifecycle import CapitalAllocationPlan, PortfolioRecommendation, PromotionRecommendation, RetirementRecommendation
from app.services.lifecycle.strategy_lifecycle_manager import lifecycle_manager
from app.services.allocation.capital_allocator import capital_allocator
from app.schemas.lifecycle import TierLimits
from app.services.audit.audit_logger import emit as audit_emit
from app.services.control.control_plane import control_plane


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


class AutonomousPortfolioManager(SafeRedisMixin):
    REC_PREFIX = "portfolio:recommendations"

    def __init__(self):
        self._local_recs: list[PortfolioRecommendation] = []

    async def run_review(self, strategies: list[dict]) -> PortfolioRecommendation:
        await audit_emit("portfolio.review.start", "portfolio", "system", {})

        mode = await self._safe_read_execution_mode()
        if mode == "disabled":
            await audit_emit("portfolio.review.skipped", "portfolio", "system", {"reason": "disabled"})
            rec = PortfolioRecommendation(generated_at=datetime.now(timezone.utc).isoformat())
            self._local_recs.append(rec)
            return rec

        promotions = await lifecycle_manager.evaluate_promotions(strategies)
        retirements = await lifecycle_manager.evaluate_retirements(strategies)

        # Determine active set (exclude retirement candidates and SHADOW)
        retire_ids = {r.strategy_id for r in retirements}
        active = [s for s in strategies if s.get("strategy_id") not in retire_ids and s.get("tier") in ("PAPER", "LIVE")]

        # Augment strategies with rank info for allocation
        total = max(len(active), 1)
        for i, s in enumerate(active):
            s["rank"] = s.get("rank", i + 1)
            s["total_strategies"] = total

        limits = TierLimits()
        plan = capital_allocator.allocate(active, mode="balanced", limits=limits)

        await capital_allocator.persist_plan(plan)

        rec = PortfolioRecommendation(
            active_strategies=[{
                "strategy_id": s.get("strategy_id", ""),
                "tier": s.get("tier", ""),
                "sharpe": s.get("sharpe", 0.0),
                "health": s.get("health_score", 0.0),
                "confidence": s.get("confidence", 0.0),
                "rank": s.get("rank", 0),
            } for s in active],
            retirement_candidates=retirements,
            promotion_candidates=promotions,
            allocation_plan=plan,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_recs.append(rec)
        await self._safe_redis("rpush", self.REC_PREFIX, rec.model_dump_json())
        await audit_emit("portfolio.review.complete", "portfolio", "system", {
            "active": len(active), "promotions": len(promotions), "retirements": len(retirements),
        })
        return rec

    async def get_latest_recommendation(self) -> PortfolioRecommendation | None:
        raw = await self._safe_redis("lrange", self.REC_PREFIX, -1, -1)
        if raw:
            try:
                return PortfolioRecommendation.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_recs[-1] if self._local_recs else None

    async def get_recommendation_history(self) -> list[PortfolioRecommendation]:
        raw = await self._safe_redis("lrange", self.REC_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioRecommendation.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_recs)

    async def _safe_read_execution_mode(self) -> str:
        try:
            return await control_plane.get_execution_mode()
        except Exception:
            return "shadow"


portfolio_manager = AutonomousPortfolioManager()