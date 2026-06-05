from datetime import datetime, timezone
from typing import Any

from app.schemas.lifecycle import GovernanceRecord, PromotionRecommendation, RetirementRecommendation, CapitalAllocationPlan
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


class StrategyGovernance(SafeRedisMixin):
    RECORD_PREFIX = "governance:records"

    def __init__(self):
        self._local_records: list[GovernanceRecord] = []

    def explain_promotion(self, promo: PromotionRecommendation, details: dict | None = None) -> GovernanceRecord:
        lines = [
            f"Promoted from {promo.current_tier} to {promo.recommended_tier}",
        ]
        for r in promo.reasons:
            lines.append(f"- {r}")
        lines.append(f"Score: {promo.score:.1f}")
        lines.append(f"Source: {promo.source}")

        record = GovernanceRecord(
            record_id=f"gov-promo-{promo.strategy_id[:8]}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            strategy_id=promo.strategy_id,
            decision_type="promotion",
            reasoning="\n".join(lines),
            details={
                "from_tier": promo.current_tier,
                "to_tier": promo.recommended_tier,
                "score": promo.score,
                "reasons": promo.reasons,
                "source": promo.source,
                **(details or {}),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_records.append(record)
        return record

    def explain_retirement(self, retire: RetirementRecommendation, details: dict | None = None) -> GovernanceRecord:
        lines = [f"Retirement recommended for {retire.strategy_id}"]
        for t in retire.triggers:
            lines.append(f"- {t}")
        lines.append(f"Retirement score: {retire.score:.1f}")

        record = GovernanceRecord(
            record_id=f"gov-retire-{retire.strategy_id[:8]}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            strategy_id=retire.strategy_id,
            decision_type="retirement",
            reasoning="\n".join(lines),
            details={
                "triggers": retire.triggers,
                "score": retire.score,
                "reason": retire.reason,
                **(details or {}),
            },
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_records.append(record)
        return record

    def explain_allocation(self, plan: CapitalAllocationPlan, details: dict | None = None) -> list[GovernanceRecord]:
        records = []
        for alloc in plan.allocations:
            lines = [
                f"Allocation for {alloc.strategy_id} ({alloc.tier})",
                f"- {alloc.allocation_pct}% of capital",
                f"- Confidence: {alloc.confidence:.2f}",
                f"- Health: {alloc.health:.1f}",
                f"- Sharpe: {alloc.sharpe:.2f}",
                f"- Rank: #{alloc.rank}",
            ]
            record = GovernanceRecord(
                record_id=f"gov-alloc-{alloc.strategy_id[:8]}-{datetime.now(timezone.utc).strftime('%H%M%S')}",
                strategy_id=alloc.strategy_id,
                decision_type="allocation",
                reasoning="\n".join(lines),
                details={
                    "allocation_pct": alloc.allocation_pct,
                    "tier": alloc.tier,
                    "confidence": alloc.confidence,
                    "health": alloc.health,
                    "sharpe": alloc.sharpe,
                    "rank": alloc.rank,
                    **(details or {}),
                },
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            records.append(record)
            self._local_records.append(record)
        return records

    async def persist(self, record: GovernanceRecord) -> None:
        await self._safe_redis("rpush", self.RECORD_PREFIX, record.model_dump_json())
        await audit_emit("governance.record.created", "governance", "system", {
            "record_id": record.record_id, "decision": record.decision_type,
        })

    async def get_records(self) -> list[GovernanceRecord]:
        raw = await self._safe_redis("lrange", self.RECORD_PREFIX, 0, -1)
        if raw:
            try:
                return [GovernanceRecord.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_records)

    async def get_promotion_records(self) -> list[GovernanceRecord]:
        return [r for r in await self.get_records() if r.decision_type == "promotion"]

    async def get_retirement_records(self) -> list[GovernanceRecord]:
        return [r for r in await self.get_records() if r.decision_type == "retirement"]

    async def get_allocation_records(self) -> list[GovernanceRecord]:
        return [r for r in await self.get_records() if r.decision_type == "allocation"]


governance = StrategyGovernance()