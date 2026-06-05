import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.control import (
    PortfolioControlReport, StabilizedPortfolioState,
    StabilityAdjustmentReport, FeedbackDampeningReport,
    PortfolioDriftReport, RegimeTransitionControlReport,
)
from app.services.control.stability_controller_service import stability_controller
from app.services.control.feedback_dampening_service import feedback_dampening_service
from app.services.control.portfolio_drift_detector import portfolio_drift_detector
from app.services.control.regime_transition_controller import regime_transition_controller
from app.services.audit.audit_logger import emit as audit_emit
from app.core.metrics import portfolio_stability_score, allocation_drift_events, feedback_dampening_adjustments, regime_stability_updates


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


class AutonomousControlPipeline(SafeRedisMixin):
    REPORT_PREFIX = "control:reports"

    def __init__(self):
        self._local_reports: list[PortfolioControlReport] = []

    async def run(
        self,
        current_weights: dict[str, float] | None = None,
        previous_weights: dict[str, float] | None = None,
        regime_probabilities: dict[str, float] | None = None,
        previous_regime_probs: dict[str, float] | None = None,
        equilibrium_weights: dict[str, float] | None = None,
        risk_penalties: dict[str, float] | None = None,
        learning_signals: dict[str, float] | None = None,
        volatility_estimate: float = 0.0,
        regime_instability: float = 0.0,
        allocation_variance: float = 0.0,
        current_regime: str = "",
        predicted_regime_probs: dict[str, float] | None = None,
        realized_regime_probs: dict[str, float] | None = None,
        current_covariance: dict[str, dict[str, float]] | None = None,
        baseline_covariance: dict[str, dict[str, float]] | None = None,
        volatility_shock: float = 0.0,
        signal_divergence_detected: bool = False,
        drift_threshold: float = 30.0,
        seed: int | None = None,
    ) -> PortfolioControlReport:
        await audit_emit("control.pipeline.start", "control", "pipeline", {})

        cw = current_weights or {}
        eq_w = equilibrium_weights or cw

        stability_report = await stability_controller.apply_stability_constraints(
            current_weights=cw,
            previous_weights=previous_weights,
            regime_probabilities=regime_probabilities,
            previous_regime_probabilities=previous_regime_probs,
            risk_penalties=risk_penalties,
        )
        portfolio_stability_score.set(100.0 - stability_report.total_turnover_pct)

        ls = learning_signals or {}
        dampening_report = await feedback_dampening_service.dampen(
            learning_signals=ls,
            volatility_estimate=volatility_estimate,
            regime_instability=regime_instability,
            allocation_variance=allocation_variance,
        )
        feedback_dampening_adjustments.inc(len(ls))

        drift_report = await portfolio_drift_detector.detect_drift(
            current_weights=cw,
            equilibrium_weights=eq_w,
            predicted_regime_probs=predicted_regime_probs,
            realized_regime_probs=realized_regime_probs,
            current_covariance=current_covariance,
            baseline_covariance=baseline_covariance,
            drift_threshold=drift_threshold,
        )
        if drift_report.overall_drift_score > drift_threshold:
            allocation_drift_events.inc()

        regime_report = await regime_transition_controller.stabilize(
            current_regime=current_regime,
            regime_probabilities=regime_probabilities,
            predicted_next_probs=predicted_regime_probs,
            volatility_shock=volatility_shock,
            signal_divergence_detected=signal_divergence_detected,
        )
        regime_stability_updates.inc()

        stabilized_state = [
            StabilizedPortfolioState(
                strategy_id=sa.strategy_id,
                stabilized_weight_pct=sa.stabilized_weight_pct,
                drift_from_optimal=round(abs(sa.stabilized_weight_pct - eq_w.get(sa.strategy_id, 0.0) * 100), 4),
            )
            for sa in stability_report.allocations
        ]

        report = PortfolioControlReport(
            report_id=f"ctrl-{str(uuid.uuid4())[:8]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            stability=stability_report,
            dampening=dampening_report,
            drift=drift_report,
            regime_transitions=regime_report,
            stabilized_state=stabilized_state,
            summary=f"Stability turnover {stability_report.total_turnover_pct}%, "
                    f"drift score {drift_report.overall_drift_score}, "
                    f"regimes: {len(regime_report.regimes)}",
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.REPORT_PREFIX, report.model_dump_json())
        await audit_emit("control.pipeline.completed", "control", "pipeline", {
            "report_id": report.report_id,
            "drift_score": drift_report.overall_drift_score,
        })
        return report

    async def get_latest(self) -> PortfolioControlReport | None:
        raw = await self._safe_redis("lrange", self.REPORT_PREFIX, -1, -1)
        if raw:
            try:
                return PortfolioControlReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None

    async def get_reports(self) -> list[PortfolioControlReport]:
        raw = await self._safe_redis("lrange", self.REPORT_PREFIX, 0, -1)
        if raw:
            try:
                return [PortfolioControlReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)


autonomous_control_pipeline = AutonomousControlPipeline()
