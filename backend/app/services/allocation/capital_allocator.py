from datetime import datetime, timezone
from typing import Any

from app.schemas.lifecycle import CapitalAllocationPlan, StrategyAllocation, TierLimits
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


class CapitalAllocator(SafeRedisMixin):
    PLAN_PREFIX = "allocation:plans"

    def __init__(self):
        self._local_plans: list[CapitalAllocationPlan] = []

    def allocate(self, strategies: list[dict], mode: str = "balanced", limits: TierLimits | None = None) -> CapitalAllocationPlan:
        if limits is None:
            limits = TierLimits()

        if not strategies:
            return CapitalAllocationPlan(mode=mode, generated_at=datetime.now(timezone.utc).isoformat())

        scored = self._score_strategies(strategies, mode)
        if mode == "auto":
            # auto = use tournament ranking distribution
            mode = self._detect_mode(strategies)

        raw_allocations = self._compute_raw(scored, mode, limits)
        normalized = self._normalize(raw_allocations, limits)

        plan = CapitalAllocationPlan(
            allocations=normalized,
            total_pct=round(sum(a.allocation_pct for a in normalized), 2),
            mode=mode,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_plans.append(plan)
        return plan

    def _score_strategies(self, strategies: list[dict], mode: str) -> list[tuple[dict, float]]:
        scored = []
        for s in strategies:
            tier = s.get("tier", "SHADOW")
            if tier == "SHADOW":
                scored.append((s, 0.0))
                continue

            sharpe = min(s.get("sharpe", 0.0), 3.0)
            health = s.get("health_score", 50.0) / 100.0
            conf = s.get("confidence", 0.0)
            rank = s.get("rank", 999)
            total = max(s.get("total_strategies", 1), 1)
            drawdown = s.get("drawdown", 0.0)

            rank_score = max(0.0, 1.0 - (rank - 1) / total)
            dd_score = 1.0 - min(drawdown, 0.5)

            if mode == "conservative":
                score = health * 0.35 + dd_score * 0.3 + rank_score * 0.2 + (sharpe / 3.0) * 0.1 + conf * 0.05
            elif mode == "aggressive":
                score = (sharpe / 3.0) * 0.35 + rank_score * 0.25 + conf * 0.2 + health * 0.1 + dd_score * 0.1
            else:
                score = (sharpe / 3.0) * 0.25 + health * 0.2 + dd_score * 0.2 + rank_score * 0.2 + conf * 0.15

            scored.append((s, max(0.0, score)))

        return scored

    def _compute_raw(self, scored: list[tuple[dict, float]], mode: str, limits: TierLimits) -> list[StrategyAllocation]:
        total_score = sum(s for _, s in scored)
        if total_score == 0:
            return []

        result = []
        for s, score in scored:
            tier = s.get("tier", "SHADOW")
            if tier == "SHADOW" or score <= 0:
                continue
            raw_pct = (score / total_score) * 100.0
            result.append(StrategyAllocation(
                strategy_id=s.get("strategy_id", ""),
                tier=tier,
                allocation_pct=round(raw_pct, 2),
                confidence=s.get("confidence", 0.0),
                health=s.get("health_score", 50.0),
                sharpe=s.get("sharpe", 0.0),
                rank=s.get("rank", 0),
            ))
        return result

    def _normalize(self, allocations: list[StrategyAllocation], limits: TierLimits) -> list[StrategyAllocation]:
        if not allocations:
            return []

        for a in allocations:
            a.allocation_pct = max(a.allocation_pct, limits.min_allocation_pct)

        total = sum(a.allocation_pct for a in allocations)
        if total > 100.0:
            for a in allocations:
                a.allocation_pct = round(a.allocation_pct / total * 100.0, 2)

        # Iteratively apply caps and redistribute
        for _ in range(20):
            excess = 0.0
            room_total = 0.0
            for a in allocations:
                max_pct = self._get_max_pct(a.tier, limits)
                if max_pct <= 0:
                    continue
                if a.allocation_pct > max_pct:
                    excess += a.allocation_pct - max_pct
                    a.allocation_pct = max_pct

            if excess < 0.01:
                break

            for a in allocations:
                max_pct = self._get_max_pct(a.tier, limits)
                if max_pct > 0 and a.allocation_pct < max_pct:
                    room_total += max_pct - a.allocation_pct

            if room_total <= 0:
                break

            for a in allocations:
                max_pct = self._get_max_pct(a.tier, limits)
                if max_pct > 0 and a.allocation_pct < max_pct:
                    room = max_pct - a.allocation_pct
                    a.allocation_pct = round(a.allocation_pct + excess * (room / room_total), 2)

        # Final adjustment to sum to 100%
        final_total = sum(a.allocation_pct for a in allocations)
        if abs(final_total - 100.0) > 0.01 and allocations:
            candidates = [a for a in allocations if self._get_max_pct(a.tier, limits) <= 0 or a.allocation_pct < self._get_max_pct(a.tier, limits)]
            if not candidates:
                candidates = allocations
            diff = round(100.0 - final_total, 2)
            candidates[0].allocation_pct = round(candidates[0].allocation_pct + diff, 2)

        return allocations

    def _get_max_pct(self, tier: str, limits: TierLimits) -> float:
        if tier == "LIVE":
            return limits.live_max_pct
        elif tier == "PAPER":
            return limits.paper_max_pct
        elif tier == "SHADOW":
            return limits.shadow_max_pct
        return 100.0

    def _detect_mode(self, strategies: list[dict]) -> str:
        avg_health = sum(s.get("health_score", 50) for s in strategies) / max(len(strategies), 1)
        avg_sharpe = sum(s.get("sharpe", 0) for s in strategies) / max(len(strategies), 1)
        if avg_health >= 75 and avg_sharpe >= 1.5:
            return "aggressive"
        elif avg_health >= 50 and avg_sharpe >= 0.5:
            return "balanced"
        return "conservative"

    async def persist_plan(self, plan: CapitalAllocationPlan) -> None:
        await self._safe_redis("rpush", self.PLAN_PREFIX, plan.model_dump_json())
        await audit_emit("allocation.plan.generated", "allocation", "system", {
            "mode": plan.mode, "strategies": len(plan.allocations),
        })

    async def get_plans(self) -> list[CapitalAllocationPlan]:
        raw = await self._safe_redis("lrange", self.PLAN_PREFIX, 0, -1)
        if raw:
            try:
                return [CapitalAllocationPlan.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_plans)


capital_allocator = CapitalAllocator()