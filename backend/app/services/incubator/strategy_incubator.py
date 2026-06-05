from datetime import datetime, timezone
from typing import Any

from app.schemas.research_memory import IncubationDecision, CandidateRecommendation
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


class StrategyIncubator(SafeRedisMixin):
    DECISION_PREFIX = "incubator:decisions"

    def __init__(self):
        self._local_decisions: list[IncubationDecision] = []

    async def evaluate(self, candidate: CandidateRecommendation, existing_strategies: list[dict] | None = None) -> IncubationDecision:
        reasons: list[str] = []
        approved = True

        if candidate.confidence < 0.3:
            reasons.append(f"Confidence {candidate.confidence:.2f} below threshold (0.3)")
            approved = False

        if candidate.novelty_score < 0.2:
            reasons.append(f"Novelty {candidate.novelty_score:.2f} below threshold (0.2)")
            approved = False

        if candidate.diversity_score < 0.2:
            reasons.append(f"Diversity {candidate.diversity_score:.2f} below threshold (0.2)")
            approved = False

        if existing_strategies:
            similar = [s for s in existing_strategies if s.get("archetype") == candidate.archetype]
            if len(similar) >= 3 and candidate.diversity_score < 0.5:
                reasons.append(f"Too many similar strategies ({len(similar)}) with low diversity")
                approved = False

        if approved:
            reasons.append(f"Confidence {candidate.confidence:.2f}")
            reasons.append(f"Novelty {candidate.novelty_score:.2f}")
            reasons.append(f"Diversity {candidate.diversity_score:.2f}")
        else:
            reasons.insert(0, "Incubation blocked")

        decision = IncubationDecision(
            strategy_id=candidate.strategy_id,
            from_status="EXPERIMENTAL",
            to_status="SHADOW",
            reasons=reasons,
            approved=approved,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_decisions.append(decision)
        await self._safe_redis("rpush", self.DECISION_PREFIX, decision.model_dump_json())

        if approved:
            await audit_emit("candidate.incubated", "incubator", "research", {
                "strategy_id": candidate.strategy_id, "archetype": candidate.archetype,
            })

        return decision

    async def get_decisions(self) -> list[IncubationDecision]:
        raw = await self._safe_redis("lrange", self.DECISION_PREFIX, 0, -1)
        if raw:
            try:
                return [IncubationDecision.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_decisions)


incubator = StrategyIncubator()