import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.optimization import PortfolioOptimizationReport
from app.services.optimization.portfolio_optimization_engine import portfolio_optimization_engine
from app.services.optimization.regime_expected_return_model import regime_expected_return_model
from app.services.optimization.risk_model_service import risk_model_service
from app.services.optimization.monte_carlo_simulation_service import monte_carlo_simulation_service
from app.services.optimization.allocation_learning_service import allocation_learning_service
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


class AutonomousOptimizationPipeline(SafeRedisMixin):
    REPORT_PREFIX = "optimization:reports"

    def __init__(self):
        self._local_reports: list[PortfolioOptimizationReport] = []

    async def run(
        self,
        strategy_ids: list[str] | None = None,
        expected_returns_map: dict[str, float] | None = None,
        regime_probabilities: dict[str, float] | None = None,
        strategy_performance_by_regime: dict[str, dict[str, float]] | None = None,
        base_correlations: dict[str, dict[str, float]] | None = None,
        tier_caps: dict[str, float] | None = None,
        current_weights: dict[str, float] | None = None,
        actual_returns: dict[str, float] | None = None,
        regime_accuracy: dict[str, float] | None = None,
        stress_survivability: dict[str, float] | None = None,
        regime: str = "low_volatility",
        seed: int | None = None,
    ) -> PortfolioOptimizationReport:
        await audit_emit("optimization.pipeline.start", "optimization", "pipeline", {})

        try:
            from app.services.control.control_plane import control_plane
            state = await control_plane.get_state()
            if not state.get("trading_enabled", True):
                await audit_emit("optimization.pipeline.skipped", "optimization", "pipeline", {"reason": "disabled"})
                report = PortfolioOptimizationReport(
                    report_id=f"opt-{str(uuid.uuid4())[:8]}",
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    summary="Optimization skipped: trading disabled",
                )
                self._local_reports.append(report)
                await self._safe_redis("rpush", self.REPORT_PREFIX, report.model_dump_json())
                return report
        except Exception:
            pass

        er_map = expected_returns_map or {}
        sids = strategy_ids or list(er_map.keys())
        regime_probs = regime_probabilities or {regime: 1.0}
        caps = tier_caps or {}
        curr_w = current_weights or {s: 1.0 / max(len(sids), 1) for s in sids}

        expected_returns_output = await regime_expected_return_model.compute(
            regime_probabilities=regime_probs,
            strategy_performance_by_regime=strategy_performance_by_regime or {},
            confidence_weights=regime_probs,
        )

        risk_output = await risk_model_service.compute(
            strategy_ids=sids,
            base_correlations=base_correlations,
            regime=regime,
        )

        mc_report = await monte_carlo_simulation_service.simulate(
            strategy_ids=sids,
            weights=[curr_w.get(s, 0.0) for s in sids],
            covariance=risk_output.correlations if risk_output else None,
            expected_returns=er_map,
            starting_regime=regime,
            seed=seed,
        )

        opt_output = await portfolio_optimization_engine.optimize_portfolio(
            strategy_ids=sids,
            expected_returns=er_map,
            covariance=risk_output.correlations if risk_output else None,
            regime=regime,
            tier_caps=caps,
            seed=seed,
        )

        learning_output = await allocation_learning_service.update(
            current_weights=curr_w,
            expected_returns=er_map,
            actual_returns=actual_returns,
            regime_accuracy=regime_accuracy,
            stress_survivability=stress_survivability,
            tier_caps=caps,
            seed=seed,
        )

        report = PortfolioOptimizationReport(
            report_id=f"opt-{str(uuid.uuid4())[:8]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            allocation=opt_output,
            expected_returns=expected_returns_output,
            risk_model=risk_output,
            monte_carlo=mc_report,
            learning=learning_output,
            summary=f"Optimized {len(opt_output.allocations)} strategies, "
                    f"MC expected drawdown {mc_report.expected_drawdown:.2%}, "
                    f"learning updates: {len(learning_output.updates)}",
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.REPORT_PREFIX, report.model_dump_json())
        await audit_emit("optimization.completed", "optimization", "pipeline", {
            "report_id": report.report_id,
            "strategies": len(opt_output.allocations),
        })
        return report

    async def get_reports(self) -> list[PortfolioOptimizationReport]:
        raw = await self._safe_redis("lrange", self.REPORT_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioOptimizationReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)

    async def get_latest(self) -> PortfolioOptimizationReport | None:
        reports = await self.get_reports()
        return reports[-1] if reports else None


autonomous_optimization_pipeline = AutonomousOptimizationPipeline()
