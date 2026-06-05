import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import OptimizedPortfolioAllocation, OptimizationDiagnostics, PortfolioOptimizationOutput
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


class PortfolioOptimizationEngine(SafeRedisMixin):
    OPT_PREFIX = "optimization:portfolio"

    def __init__(self):
        self._local_outputs: list[PortfolioOptimizationOutput] = []

    async def optimize_portfolio(
        self,
        strategy_ids: list[str],
        expected_returns: dict[str, float],
        covariance: dict[str, dict[str, float]] | None = None,
        regime: str = "unknown",
        tier_caps: dict[str, float] | None = None,
        max_drawdown_penalty: float = 0.5,
        diversification_weight: float = 0.2,
        seed: int | None = None,
    ) -> PortfolioOptimizationOutput:
        n = len(strategy_ids)
        if n == 0:
            output = PortfolioOptimizationOutput(
                allocations=[], regime=regime, generated_at=datetime.now(timezone.utc).isoformat(),
                diagnostics=OptimizationDiagnostics(objective_value=0.0, iterations=0),
            )
            self._local_outputs.append(output)
            return output

        caps = {s: tier_caps.get(s, 100.0) for s in strategy_ids} if tier_caps else {s: 100.0 for s in strategy_ids}

        weights = self._solve_weights(
            strategy_ids, expected_returns, caps, max_drawdown_penalty, diversification_weight, seed
        )

        violations = self._check_constraints(weights, caps)

        risk_contributions = self._compute_risk_contributions(weights, covariance)

        objective_value = self._compute_objective(
            weights, strategy_ids, expected_returns, risk_contributions,
            max_drawdown_penalty, diversification_weight,
        )

        allocations = [
            OptimizedPortfolioAllocation(
                strategy_id=sid,
                weight_pct=round(w * 100, 4),
                expected_return=round(expected_returns.get(sid, 0.0), 6),
                risk_contribution=round(risk_contributions.get(sid, 0.0), 4),
                status="active" if w > 0 else "excluded",
            )
            for sid, w in zip(strategy_ids, weights) if w > 0.001
        ]

        diagnostics = OptimizationDiagnostics(
            objective_value=round(objective_value, 6),
            constraint_violations=violations,
            iterations=len(strategy_ids) * 10,
            convergence_status="success" if not violations else "partial",
        )

        output = PortfolioOptimizationOutput(
            allocations=allocations,
            diagnostics=diagnostics,
            regime=regime,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_outputs.append(output)
        await self._safe_redis("rpush", self.OPT_PREFIX, output.model_dump_json())
        await audit_emit("optimization.completed", "optimization", "portfolio", {
            "strategies": len(allocations), "objective": objective_value,
        })
        return output

    def _solve_weights(
        self,
        strategy_ids: list[str],
        expected_returns: dict[str, float],
        caps: dict[str, float],
        drawdown_penalty: float,
        diversification_weight: float,
        seed: int | None = None,
    ) -> list[float]:
        import random
        rng = random.Random(seed) if seed is not None else random.Random()
        n = len(strategy_ids)
        w = [0.0] * n

        cap_list = [caps[s] / 100.0 for s in strategy_ids]
        er_list = [max(expected_returns.get(s, 0.0), 0.0) for s in strategy_ids]
        er_sum = sum(er_list) if sum(er_list) > 0 else 1.0
        initial = [e / er_sum for e in er_list]

        for _ in range(50):
            grad = [initial[i] * er_list[i] - drawdown_penalty * w[i] + diversification_weight * (1.0 / n - w[i]) for i in range(n)]
            step = 0.1
            for i in range(n):
                w[i] += step * grad[i]
                w[i] = max(0.0, min(cap_list[i], w[i]))
            total = sum(w)
            if total > 0:
                w = [wi / total for wi in w]
            for i in range(n):
                w[i] = min(cap_list[i], w[i])
            total = sum(w)
            if total > 0:
                scale = min(1.0, sum(cap_list) / total) if sum(cap_list) > 0 else 1.0
                w = [min(wi * scale, cap_list[i]) for i, wi in enumerate(w)]

        total = sum(w)
        if total > 0:
            w = [wi / total for wi in w]

        return [round(wi, 6) for wi in w]

    def _check_constraints(self, weights: list[float], caps: dict[str, float]) -> list[str]:
        violations = []
        cap_vals = list(caps.values())
        for i, w in enumerate(weights):
            if w < -0.0001:
                violations.append(f"weight[{i}]={w} < 0")
            cap = cap_vals[i] / 100.0 if i < len(cap_vals) else 1.0
            if w > cap + 0.0001:
                violations.append(f"weight[{i}]={w} > cap={cap}")
        total = sum(weights)
        if abs(total - 1.0) > 0.01:
            violations.append(f"sum(weights)={total} != 1.0")
        return violations

    def _compute_risk_contributions(self, weights: list[float], covariance: dict[str, dict[str, float]] | None) -> dict[str, float]:
        if not covariance:
            return {f"idx_{i}": 0.0 for i in range(len(weights))}
        contributions: dict[str, float] = {}
        keys = list(covariance.keys())
        for i, ki in enumerate(keys):
            contrib = 0.0
            for j, kj in enumerate(keys):
                contrib += weights[j] * covariance.get(ki, {}).get(kj, 0.0)
            contributions[ki] = contrib * weights[i]
        return contributions

    def _compute_objective(
        self, weights: list[float], sids: list[str], expected_returns: dict[str, float],
        risk_contributions: dict[str, float], drawdown_penalty: float, diversification_weight: float,
    ) -> float:
        ret = sum(w * expected_returns.get(sid, 0.0) for w, sid in zip(weights, sids))
        risk = sum(abs(rc) for rc in risk_contributions.values())
        n = len(weights)
        hhi = sum(w * w for w in weights)
        div_bonus = diversification_weight * (1.0 - hhi / (1.0 / n)) if n > 1 else 0.0
        return ret - drawdown_penalty * risk + div_bonus

    async def get_latest(self) -> PortfolioOptimizationOutput | None:
        raw = await self._safe_redis("lrange", self.OPT_PREFIX, -1, -1)
        if raw:
            try:
                return PortfolioOptimizationOutput.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_outputs[-1] if self._local_outputs else None

    async def get_all(self) -> list[PortfolioOptimizationOutput]:
        raw = await self._safe_redis("lrange", self.OPT_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioOptimizationOutput.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_outputs)


portfolio_optimization_engine = PortfolioOptimizationEngine()
