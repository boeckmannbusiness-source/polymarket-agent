from datetime import datetime, timezone
from typing import Any

from app.schemas.lifecycle import PromotionRecommendation, RetirementRecommendation, LifecycleDecision
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


class StrategyLifecycleManager(SafeRedisMixin):
    PROMO_PREFIX = "lifecycle:promotions"
    RETIRE_PREFIX = "lifecycle:retirements"
    DECISION_PREFIX = "lifecycle:decisions"

    def __init__(self):
        self._local_promotions: list[PromotionRecommendation] = []
        self._local_retirements: list[RetirementRecommendation] = []
        self._local_decisions: list[LifecycleDecision] = []

    async def evaluate_promotions(self, strategies: list[dict]) -> list[PromotionRecommendation]:
        promotions: list[PromotionRecommendation] = []
        for s in strategies:
            tier = s.get("tier", "SHADOW")
            trades = s.get("total_trades", 0)
            sharpe = s.get("sharpe", 0.0)
            drawdown = s.get("drawdown", 1.0)
            confidence = s.get("confidence", 0.0)
            health = s.get("health_score", 0.0)
            rank = s.get("rank", 999)
            total_strategies = s.get("total_strategies", 1)

            if tier == "EXPERIMENTAL":
                if trades >= 30 and sharpe >= 0.5 and drawdown <= 0.15 and confidence >= 0.4 and health >= 40:
                    score = (min(sharpe, 3.0) / 3.0 * 0.3 + (1.0 - drawdown) * 0.25 + confidence * 0.25 + health / 100.0 * 0.2)
                    if score >= 0.5:
                        reasons = [f"Score {score:.2f} >= 0.5", f"{trades} trades completed", f"Sharpe {sharpe:.2f}", f"Drawdown {drawdown:.1%}"]
                        promotions.append(PromotionRecommendation(
                            strategy_id=s.get("strategy_id", ""),
                            current_tier=tier, recommended_tier="SHADOW",
                            reasons=reasons, score=round(score * 100, 1),
                            source="lifecycle_manager",
                            created_at=datetime.now(timezone.utc).isoformat(),
                        ))

            elif tier == "SHADOW":
                if trades >= 100 and sharpe >= 1.0 and drawdown <= 0.10 and confidence >= 0.6 and health >= 60 and rank <= max(3, total_strategies // 2):
                    score = (min(sharpe, 3.0) / 3.0 * 0.3 + (1.0 - drawdown) * 0.25 + confidence * 0.2 + health / 100.0 * 0.15 + max(0, 1.0 - rank / total_strategies) * 0.1)
                    if score >= 0.6:
                        reasons = [f"Score {score:.2f} >= 0.6", f"{trades} closed trades", f"Sharpe {sharpe:.2f}", f"Drawdown {drawdown:.1%}", f"Rank {rank}/{total_strategies}"]
                        promotions.append(PromotionRecommendation(
                            strategy_id=s.get("strategy_id", ""),
                            current_tier=tier, recommended_tier="PAPER",
                            reasons=reasons, score=round(score * 100, 1),
                            source="lifecycle_manager",
                            created_at=datetime.now(timezone.utc).isoformat(),
                        ))

            elif tier == "PAPER":
                if trades >= 50 and sharpe >= 0.8 and drawdown <= 0.12 and confidence >= 0.7 and health >= 70 and rank <= max(2, total_strategies // 3):
                    score = (min(sharpe, 3.0) / 3.0 * 0.25 + (1.0 - drawdown) * 0.2 + confidence * 0.2 + health / 100.0 * 0.2 + max(0, 1.0 - rank / total_strategies) * 0.15)
                    if score >= 0.65:
                        reasons = [f"Score {score:.2f} >= 0.65", f"{trades} paper trades", f"Sharpe {sharpe:.2f}", f"Drawdown {drawdown:.1%}", f"Rank {rank}/{total_strategies}"]
                        promotions.append(PromotionRecommendation(
                            strategy_id=s.get("strategy_id", ""),
                            current_tier=tier, recommended_tier="LIVE",
                            reasons=reasons, score=round(score * 100, 1),
                            source="lifecycle_manager",
                            created_at=datetime.now(timezone.utc).isoformat(),
                        ))

        for p in promotions:
            self._local_promotions.append(p)
            await self._safe_redis("rpush", self.PROMO_PREFIX, p.model_dump_json())
            await audit_emit("lifecycle.promotion.evaluated", "lifecycle", "system", {
                "strategy_id": p.strategy_id, "from": p.current_tier, "to": p.recommended_tier,
            })

        return promotions

    async def evaluate_retirements(self, strategies: list[dict]) -> list[RetirementRecommendation]:
        retirements: list[RetirementRecommendation] = []
        for s in strategies:
            triggers: list[str] = []
            health = s.get("health_score", 100.0)
            drawdown = s.get("drawdown", 0.0)
            circuit_breaker_count = s.get("circuit_breaker_count", 0)
            alpha = s.get("alpha", 0.0)
            trades = s.get("total_trades", 0)

            if health < 30:
                triggers.append(f"Health CRITICAL ({health:.0f})")
            if drawdown > 0.25:
                triggers.append(f"Drawdown {drawdown:.1%} > 25%")
            if circuit_breaker_count >= 3:
                triggers.append(f"{circuit_breaker_count} circuit breaker events")
            if alpha < -0.1:
                triggers.append(f"Negative alpha ({alpha:.2f})")
            if trades < 10:
                triggers.append(f"Insufficient activity ({trades} trades)")

            if triggers:
                score = min(1.0, len(triggers) * 0.25 + (100.0 - health) / 100.0 * 0.3 + drawdown * 0.2)
                rec = RetirementRecommendation(
                    strategy_id=s.get("strategy_id", ""),
                    reason="; ".join(triggers),
                    triggers=triggers,
                    score=round(score * 100, 1),
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
                retirements.append(rec)
                self._local_retirements.append(rec)
                await self._safe_redis("rpush", self.RETIRE_PREFIX, rec.model_dump_json())

        return retirements

    async def apply_decision(self, strategy_id: str, decision_type: str, from_tier: str | None = None, to_tier: str | None = None, reasons: list[str] | None = None) -> LifecycleDecision:
        decision = LifecycleDecision(
            strategy_id=strategy_id,
            decision_type=decision_type,
            from_tier=from_tier,
            to_tier=to_tier,
            reasons=reasons or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_decisions.append(decision)
        await self._safe_redis("rpush", self.DECISION_PREFIX, decision.model_dump_json())
        await audit_emit(f"strategy.{decision_type}", "lifecycle", "system", {
            "strategy_id": strategy_id, "from": from_tier, "to": to_tier,
        })
        return decision

    async def get_promotions(self) -> list[PromotionRecommendation]:
        raw = await self._safe_redis("lrange", self.PROMO_PREFIX, 0, -1)
        if raw:
            try:
                return [PromotionRecommendation.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_promotions)

    async def get_retirements(self) -> list[RetirementRecommendation]:
        raw = await self._safe_redis("lrange", self.RETIRE_PREFIX, 0, -1)
        if raw:
            try:
                return [RetirementRecommendation.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_retirements)

    async def get_decisions(self) -> list[LifecycleDecision]:
        raw = await self._safe_redis("lrange", self.DECISION_PREFIX, 0, -1)
        if raw:
            try:
                return [LifecycleDecision.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_decisions)


lifecycle_manager = StrategyLifecycleManager()