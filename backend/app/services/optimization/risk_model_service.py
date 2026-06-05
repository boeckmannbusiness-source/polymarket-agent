from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import RiskModelOutput
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


class RiskModelService(SafeRedisMixin):
    RISK_PREFIX = "optimization:risk"

    def __init__(self):
        self._local_outputs: list[RiskModelOutput] = []

    async def compute(
        self,
        strategy_ids: list[str],
        historical_returns: dict[str, list[float]] | None = None,
        base_correlations: dict[str, dict[str, float]] | None = None,
        regime: str = "unknown",
        correlation_spike_factor: float = 1.0,
    ) -> RiskModelOutput:
        hists = historical_returns or {}
        base_corr = base_correlations or {}

        strategies = strategy_ids or list(hists.keys())
        n = len(strategies)
        if n == 0:
            output = RiskModelOutput(
                strategies=[], regime=regime, generated_at=datetime.now(timezone.utc).isoformat(),
            )
            self._local_outputs.append(output)
            return output

        cov_matrix = self._estimate_covariance(strategies, hists, base_corr, correlation_spike_factor)
        correlations = self._correlations_from_covariance(strategies, cov_matrix)
        adjustment_factor = self._compute_adjustment(regime, correlation_spike_factor)

        output = RiskModelOutput(
            strategies=strategies,
            covariance_matrix=cov_matrix,
            correlations=correlations,
            adjustment_factor=round(adjustment_factor, 4),
            regime=regime,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_outputs.append(output)
        await self._safe_redis("rpush", self.RISK_PREFIX, output.model_dump_json())
        await audit_emit("risk.model.updated", "optimization", "risk", {
            "strategies": n, "regime": regime,
        })
        return output

    def _estimate_covariance(
        self,
        strategies: list[str],
        historical_returns: dict[str, list[float]],
        base_correlations: dict[str, dict[str, float]],
        spike_factor: float,
    ) -> list[list[float]]:
        n = len(strategies)
        cov = [[0.0] * n for _ in range(n)]

        if base_correlations:
            for i in range(n):
                for j in range(n):
                    si, sj = strategies[i], strategies[j]
                    corr = base_correlations.get(si, {}).get(sj, 0.0 if i != j else 1.0)
                    if i == j:
                        var = self._estimate_variance(si, historical_returns)
                        cov[i][j] = var
                    else:
                        vi = self._estimate_variance(si, historical_returns) ** 0.5
                        vj = self._estimate_variance(sj, historical_returns) ** 0.5
                        cov[i][j] = corr * spike_factor * vi * vj
        else:
            for i in range(n):
                for j in range(n):
                    if i == j:
                        cov[i][j] = self._estimate_variance(strategies[i], historical_returns)
                    else:
                        vi = self._estimate_variance(strategies[i], historical_returns) ** 0.5
                        vj = self._estimate_variance(strategies[j], historical_returns) ** 0.5
                        cov[i][j] = 0.0

        cov = self._enforce_psd(cov, n)
        return cov

    def _estimate_variance(self, strategy_id: str, historical_returns: dict[str, list[float]]) -> float:
        rets = historical_returns.get(strategy_id, [])
        if len(rets) < 2:
            return 0.01
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return max(var, 0.0001)

    def _enforce_psd(self, matrix: list[list[float]], n: int) -> list[list[float]]:
        for i in range(n):
            if matrix[i][i] <= 0:
                matrix[i][i] = 0.01
        return matrix

    def _correlations_from_covariance(self, strategies: list[str], cov: list[list[float]]) -> dict[str, dict[str, float]]:
        n = len(strategies)
        corr: dict[str, dict[str, float]] = {}
        for i in range(n):
            si = strategies[i]
            corr[si] = {}
            for j in range(n):
                sj = strategies[j]
                vi = cov[i][i] ** 0.5
                vj = cov[j][j] ** 0.5
                if vi > 0 and vj > 0:
                    c = cov[i][j] / (vi * vj)
                    corr[si][sj] = round(max(-1.0, min(1.0, c)), 4)
                else:
                    corr[si][sj] = 1.0 if i == j else 0.0
        return corr

    def _compute_adjustment(self, regime: str, spike_factor: float) -> float:
        base = spike_factor
        if regime == "high_volatility":
            base *= 1.3
        elif regime == "correlation_spike":
            base *= 1.5
        elif regime == "illiquid":
            base *= 1.2
        return base

    async def get_latest(self) -> RiskModelOutput | None:
        raw = await self._safe_redis("lrange", self.RISK_PREFIX, -1, -1)
        if raw:
            try:
                return RiskModelOutput.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_outputs[-1] if self._local_outputs else None

    async def get_all(self) -> list[RiskModelOutput]:
        raw = await self._safe_redis("lrange", self.RISK_PREFIX, 0, -1)
        if raw:
            try:
                return [RiskModelOutput.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_outputs)


risk_model_service = RiskModelService()
