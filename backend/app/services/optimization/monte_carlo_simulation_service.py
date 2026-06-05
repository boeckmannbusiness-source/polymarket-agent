import uuid
import random
import math
from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import MonteCarloPortfolioReport, MonteCarloPercentilePath
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


REGIME_TRANSITIONS = {
    "trending": ["trending", "mean_reverting", "high_volatility"],
    "mean_reverting": ["mean_reverting", "trending", "low_volatility"],
    "high_volatility": ["high_volatility", "mean_reverting", "event_driven"],
    "low_volatility": ["low_volatility", "trending", "high_volatility"],
    "event_driven": ["event_driven", "high_volatility", "trending"],
    "news_driven": ["news_driven", "high_volatility", "mean_reverting"],
    "illiquid": ["illiquid", "low_volatility", "high_volatility"],
}


class MonteCarloSimulationService(SafeRedisMixin):
    MC_PREFIX = "optimization:monte_carlo"

    def __init__(self):
        self._local_reports: list[MonteCarloPortfolioReport] = []

    async def simulate(
        self,
        strategy_ids: list[str],
        weights: list[float],
        covariance: dict[str, dict[str, float]] | None = None,
        expected_returns: dict[str, float] | None = None,
        n_paths: int = 1000,
        n_steps: int = 252,
        starting_regime: str = "low_volatility",
        seed: int | None = None,
    ) -> MonteCarloPortfolioReport:
        rng = random.Random(seed) if seed is not None else random.Random()
        n = len(strategy_ids)
        if n == 0 or not weights:
            return self._empty_report(rng)

        er = expected_returns or {}
        w = [wi / 100.0 for wi in weights] if max(weights) > 1 else list(weights)

        cov_matrix = self._build_cov_matrix(strategy_ids, covariance, n)
        chol = self._cholesky(cov_matrix, n, rng)

        all_path_equities: list[list[float]] = []
        all_path_drawdowns: list[list[float]] = []
        all_sharpes: list[float] = []
        all_recoveries: list[float] = []

        for _ in range(n_paths):
            equity = [1.0]
            peak = 1.0
            current_regime = starting_regime
            in_drawdown = False
            drawdown_start = 0

            for step in range(n_steps):
                z = [rng.gauss(0, 1) for _ in range(n)]
                correlated = [sum(chol[i][j] * z[j] for j in range(n)) for i in range(n)]

                regime_mean = [er.get(sid, 0.0) / 252.0 for sid in strategy_ids]
                step_return = sum(w[i] * (regime_mean[i] + correlated[i]) for i in range(n))
                new_equity = equity[-1] * (1.0 + step_return)
                equity.append(new_equity)

                if new_equity > peak:
                    peak = new_equity
                dd = (peak - new_equity) / peak
                if dd > 0.05 and not in_drawdown:
                    in_drawdown = True
                    drawdown_start = step
                if dd < 0.01 and in_drawdown:
                    in_drawdown = False
                    all_recoveries.append(step - drawdown_start)

                if step % 63 == 0 and step > 0:
                    transitions = REGIME_TRANSITIONS.get(current_regime, ["low_volatility"])
                    current_regime = rng.choice(transitions)

            all_path_equities.append(equity)
            dd_curve = []
            pk = 1.0
            for eq in equity:
                if eq > pk:
                    pk = eq
                dd_curve.append((pk - eq) / pk)
            all_path_drawdowns.append(dd_curve)

            annual_return = equity[-1] ** (252.0 / n_steps) - 1.0
            daily_rets = [(equity[i+1] / equity[i] - 1.0) for i in range(n_steps)]
            mean_daily = sum(daily_rets) / len(daily_rets) if daily_rets else 0.0
            var_daily = sum((r - mean_daily) ** 2 for r in daily_rets) / len(daily_rets) if daily_rets else 0.0001
            annual_vol = math.sqrt(var_daily * 252)
            rf = 0.0
            sharpe = (annual_return - rf) / annual_vol if annual_vol > 0 else 0.0
            all_sharpes.append(sharpe)

        expected_dd = sum(max(dd) for dd in all_path_drawdowns) / n_paths
        worst_dd = max(max(dd) for dd in all_path_drawdowns)
        recovery_mean = sum(all_recoveries) / len(all_recoveries) if all_recoveries else n_steps
        survival = sum(1 for eq in all_path_equities if eq[-1] > 0) / n_paths
        sharpe_mean = sum(all_sharpes) / n_paths
        sharpe_var = sum((s - sharpe_mean) ** 2 for s in all_sharpes) / n_paths
        sharpe_std = math.sqrt(sharpe_var)

        percentile_paths = self._compute_percentile_paths(all_path_equities, all_path_drawdowns)

        report = MonteCarloPortfolioReport(
            simulation_id=f"mc-{str(uuid.uuid4())[:8]}",
            n_paths=n_paths,
            n_steps=n_steps,
            expected_drawdown=round(expected_dd, 4),
            worst_drawdown=round(worst_dd, 4),
            recovery_time_hours=round(recovery_mean * 6.5, 2),
            survival_probability=round(survival, 4),
            sharpe_mean=round(sharpe_mean, 4),
            sharpe_std=round(sharpe_std, 4),
            percentile_paths=percentile_paths,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.MC_PREFIX, report.model_dump_json())
        await audit_emit("simulation.completed", "optimization", "monte_carlo", {
            "simulation_id": report.simulation_id,
            "n_paths": n_paths, "expected_drawdown": expected_dd,
        })
        return report

    def _compute_percentile_paths(
        self, equities: list[list[float]], drawdowns: list[list[float]],
    ) -> list[MonteCarloPercentilePath]:
        n_steps = len(equities[0]) if equities else 0
        percentiles = {"p5": 5, "p25": 25, "p50": 50, "p75": 75, "p95": 95}
        result: list[MonteCarloPercentilePath] = []

        for label, pct in percentiles.items():
            eq_curve = []
            dd_curve = []
            for step in range(n_steps):
                step_eqs = sorted(eq[step] for eq in equities)
                step_dds = sorted(dd[step] for dd in drawdowns)
                idx = int(len(step_eqs) * pct / 100)
                idx = min(idx, len(step_eqs) - 1)
                eq_curve.append(round(step_eqs[idx], 6))
                dd_curve.append(round(step_dds[idx], 6))
            result.append(MonteCarloPercentilePath(percentile=label, equity_curve=eq_curve, drawdown_curve=dd_curve))

        return result

    def _build_cov_matrix(self, sids: list[str], covariance: dict[str, dict[str, float]] | None, n: int) -> list[list[float]]:
        cov = [[0.0] * n for _ in range(n)]
        if covariance:
            for i in range(n):
                for j in range(n):
                    si, sj = sids[i], sids[j]
                    cov[i][j] = covariance.get(si, {}).get(sj, 0.0 if i != j else 0.01)
        else:
            for i in range(n):
                cov[i][i] = 0.01
        return cov

    def _cholesky(self, matrix: list[list[float]], n: int, rng: random.Random) -> list[list[float]]:
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                s = sum(L[i][k] * L[j][k] for k in range(j))
                if i == j:
                    d = matrix[i][i] - s
                    L[i][j] = math.sqrt(max(d, 0.0001))
                else:
                    L[i][j] = (matrix[i][j] - s) / L[j][j] if L[j][j] > 0 else 0.0
        return L

    def _empty_report(self, rng: random.Random) -> MonteCarloPortfolioReport:
        return MonteCarloPortfolioReport(
            simulation_id=f"mc-{str(uuid.uuid4())[:8]}",
            n_paths=0, n_steps=0, executed_at=datetime.now(timezone.utc).isoformat(),
        )

    async def get_latest(self) -> MonteCarloPortfolioReport | None:
        raw = await self._safe_redis("lrange", self.MC_PREFIX, -1, -1)
        if raw:
            try:
                return MonteCarloPortfolioReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None

    async def get_all(self) -> list[MonteCarloPortfolioReport]:
        raw = await self._safe_redis("lrange", self.MC_PREFIX, 0, -1)
        if raw:
            try:
                return [MonteCarloPortfolioReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)


monte_carlo_simulation_service = MonteCarloSimulationService()
