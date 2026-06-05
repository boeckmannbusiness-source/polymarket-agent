import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import RegimeAllocationPlan, RegimeAdjustment
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


class RegimeAllocationService(SafeRedisMixin):
    ALLOC_PREFIX = "intelligence:regime_allocation"

    def __init__(self):
        self._local_plans: list[RegimeAllocationPlan] = []

    async def generate(
        self,
        regime: str,
        regime_confidence: float,
        current_allocations: list[dict],
        tier_caps: dict[str, float] | None = None,
        strategy_archetypes: dict[str, str] | None = None,
        seed: int | None = None,
    ) -> RegimeAllocationPlan:
        caps = tier_caps or {}
        archetypes = strategy_archetypes or {}
        adjustments: list[RegimeAdjustment] = []

        for alloc in current_allocations:
            sid = alloc.get("strategy_id", "")
            current_pct = alloc.get("allocation", 0)
            arch = archetypes.get(sid, "")
            delta, rationale, conf = self._compute_regime_adjustment(regime, arch, current_pct, caps.get(sid, 100.0), regime_confidence)
            if delta != 0:
                adjustments.append(RegimeAdjustment(
                    strategy_id=sid,
                    from_allocation=current_pct,
                    to_allocation=round(current_pct + delta, 4),
                    delta=round(delta, 4),
                    rationale=rationale,
                    confidence=round(conf, 2),
                ))

        plan = RegimeAllocationPlan(
            regime=regime,
            regime_confidence=round(regime_confidence, 2),
            adjustments=adjustments,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_plans.append(plan)
        await self._safe_redis("rpush", self.ALLOC_PREFIX, plan.model_dump_json())
        await audit_emit("regime.allocation.generated", "intelligence", "regime_allocation", {
            "regime": regime, "adjustments": len(adjustments),
        })
        return plan

    def _compute_regime_adjustment(self, regime: str, archetype: str, current: float, cap: float, confidence: float) -> tuple[float, str, float]:
        delta = 0.0
        rationale = ""
        conf = confidence

        if regime == "trending":
            if "momentum" in archetype or "trend" in archetype:
                delta = min(current * 0.2, cap - current)
                rationale = f"Increase momentum exposure during trending regime"
                conf = min(1.0, confidence + 0.1)
            elif "reversion" in archetype or "contrarian" in archetype:
                delta = -current * 0.1
                rationale = f"Reduce mean reversion during trending regime"
        elif regime == "mean_reverting":
            if "reversion" in archetype or "contrarian" in archetype:
                delta = min(current * 0.2, cap - current)
                rationale = f"Increase contrarian exposure during mean reverting regime"
                conf = min(1.0, confidence + 0.1)
            elif "momentum" in archetype or "trend" in archetype:
                delta = -current * 0.1
                rationale = f"Reduce momentum during mean reverting regime"
        elif regime == "high_volatility":
            if "breakout" in archetype or "volatility" in archetype:
                delta = min(current * 0.1, cap - current)
                rationale = f"Modest increase in volatility-adaptive strategies"
            else:
                delta = -current * 0.05
                rationale = f"Reduce concentration during high volatility"
        elif regime == "news_driven":
            if "sentiment" in archetype or "ml" in archetype or "news" in archetype:
                delta = min(current * 0.25, cap - current)
                rationale = f"Favor news-aware strategies during news driven regime"
                conf = min(1.0, confidence + 0.15)
            else:
                delta = -current * 0.05
                rationale = f"Reduce non-news strategies during news driven regime"
        elif regime == "event_driven":
            if "event" in archetype or "prediction" in archetype:
                delta = min(current * 0.2, cap - current)
                rationale = f"Increase event-driven exposure"
                conf = min(1.0, confidence + 0.1)
        elif regime == "low_volatility":
            if "arbitrage" in archetype or "range" in archetype:
                delta = min(current * 0.15, cap - current)
                rationale = f"Increase arbitrage exposure during low volatility"
        elif regime == "illiquid":
            delta = -current * 0.1
            rationale = f"Reduce all exposure during illiquid regime"

        if delta > 0 and current + delta > cap:
            delta = max(0, cap - current)
        return round(delta, 4), rationale, round(conf, 2)

    async def get_latest(self) -> RegimeAllocationPlan | None:
        raw = await self._safe_redis("lrange", self.ALLOC_PREFIX, -1, -1)
        if raw:
            try:
                return RegimeAllocationPlan.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_plans[-1] if self._local_plans else None

    async def get_all(self) -> list[RegimeAllocationPlan]:
        raw = await self._safe_redis("lrange", self.ALLOC_PREFIX, 0, -1)
        if raw:
            try:
                return [RegimeAllocationPlan.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_plans)


regime_allocation_service = RegimeAllocationService()
