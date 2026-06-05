import uuid
import random
from datetime import datetime, timezone
from typing import Any

from app.schemas.intelligence import StressTestScenario, StressTestResult
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


SCENARIO_TYPES = {
    "market_crash": {"drawdown_range": (0.3, 0.6), "recovery_range": (48, 720), "resilience_range": (10, 40)},
    "liquidity_collapse": {"drawdown_range": (0.2, 0.4), "recovery_range": (24, 168), "resilience_range": (20, 50)},
    "news_shock": {"drawdown_range": (0.1, 0.3), "recovery_range": (12, 72), "resilience_range": (40, 70)},
    "strategy_failure": {"drawdown_range": (0.05, 0.2), "recovery_range": (6, 48), "resilience_range": (50, 80)},
    "regime_shift": {"drawdown_range": (0.15, 0.35), "recovery_range": (24, 120), "resilience_range": (30, 60)},
    "correlation_spike": {"drawdown_range": (0.1, 0.25), "recovery_range": (12, 96), "resilience_range": (35, 65)},
}


class StressTestingService(SafeRedisMixin):
    SCENARIO_PREFIX = "intelligence:stress_scenarios"
    RESULT_PREFIX = "intelligence:stress_results"

    def __init__(self):
        self._local_scenarios: list[StressTestScenario] = []
        self._local_results: list[StressTestResult] = []

    async def run_scenario(
        self,
        scenario_type: str,
        strategy_health: list[dict] | None = None,
        allocations: list[dict] | None = None,
        seed: int | None = None,
    ) -> tuple[StressTestScenario, StressTestResult]:
        rng = random.Random(seed) if seed is not None else random.Random()
        scenario_id = f"st-{str(uuid.uuid4())[:8]}"

        config = SCENARIO_TYPES.get(scenario_type, SCENARIO_TYPES["market_crash"])
        drawdown = rng.uniform(*config["drawdown_range"])
        recovery = rng.uniform(*config["recovery_range"])
        resilience = rng.uniform(*config["resilience_range"])

        survivability: dict[str, float] = {}
        health_data = strategy_health or []
        for h in health_data:
            sid = h.get("strategy_id", h.get("strategy", "unknown"))
            base = h.get("score", 50)
            factor = rng.uniform(0.5, 1.5)
            surv = max(0, min(100, base * factor))
            if scenario_type in ("market_crash", "liquidity_collapse"):
                surv *= rng.uniform(0.6, 1.0)
            elif scenario_type == "strategy_failure":
                surv *= rng.uniform(0.4, 0.8)
            survivability[sid] = round(surv, 2)

        if not survivability:
            for alloc in (allocations or []):
                sid = alloc.get("strategy_id", "unknown")
                base = rng.uniform(30, 70)
                survivability[sid] = round(base, 2)

        scenario = StressTestScenario(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            parameters={"seed": seed} if seed is not None else {},
        )
        result = StressTestResult(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            expected_drawdown=round(drawdown, 4),
            recovery_time_hours=round(recovery, 2),
            resilience_score=round(resilience, 2),
            strategy_survivability=survivability,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_scenarios.append(scenario)
        self._local_results.append(result)
        await self._safe_redis("rpush", self.SCENARIO_PREFIX, scenario.model_dump_json())
        await self._safe_redis("rpush", self.RESULT_PREFIX, result.model_dump_json())
        await audit_emit("stress.test.completed", "intelligence", "stress_test", {
            "scenario_id": scenario_id, "scenario_type": scenario_type,
            "drawdown": round(drawdown, 4), "resilience": round(resilience, 2),
        })
        return scenario, result

    async def run_all_scenarios(
        self,
        strategy_health: list[dict] | None = None,
        allocations: list[dict] | None = None,
        seed: int | None = None,
    ) -> list[StressTestResult]:
        results = []
        for stype in SCENARIO_TYPES:
            _, result = await self.run_scenario(stype, strategy_health, allocations, seed)
            results.append(result)
        return results

    async def get_scenarios(self) -> list[StressTestScenario]:
        raw = await self._safe_redis("lrange", self.SCENARIO_PREFIX, 0, -1)
        if raw:
            try:
                return [StressTestScenario.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_scenarios)

    async def get_results(self) -> list[StressTestResult]:
        raw = await self._safe_redis("lrange", self.RESULT_PREFIX, 0, -1)
        if raw:
            try:
                return [StressTestResult.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_results)

    async def get_latest_results(self) -> list[StressTestResult]:
        results = await self.get_results()
        seen: set[str] = set()
        latest: list[StressTestResult] = []
        for r in reversed(results):
            if r.scenario_type not in seen:
                seen.add(r.scenario_type)
                latest.append(r)
        return latest[::-1]


stress_testing_service = StressTestingService()
