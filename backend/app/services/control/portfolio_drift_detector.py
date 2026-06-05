import math
from datetime import datetime, timezone
from typing import Any

from app.schemas.control import DriftSource, PortfolioDriftReport
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


class PortfolioDriftDetector(SafeRedisMixin):
    PREFIX = "control:drift"

    def __init__(self):
        self._local_reports: list[PortfolioDriftReport] = []

    async def detect_drift(
        self,
        current_weights: dict[str, float],
        equilibrium_weights: dict[str, float] | None = None,
        predicted_regime_probs: dict[str, float] | None = None,
        realized_regime_probs: dict[str, float] | None = None,
        current_covariance: dict[str, dict[str, float]] | None = None,
        baseline_covariance: dict[str, dict[str, float]] | None = None,
        drift_threshold: float = 30.0,
    ) -> PortfolioDriftReport:
        eq_w = equilibrium_weights or current_weights
        alloc_drift = self._compute_allocation_drift(current_weights, eq_w)
        regime_drift = self._compute_regime_drift(predicted_regime_probs, realized_regime_probs)
        risk_drift = self._compute_risk_drift(current_covariance, baseline_covariance)

        sources: list[DriftSource] = []
        total_score = 0.0
        if alloc_drift > 0:
            sources.append(DriftSource(source="allocation", contribution=round(alloc_drift, 2)))
            total_score += alloc_drift * 0.5
        if regime_drift > 0:
            sources.append(DriftSource(source="regime", contribution=round(regime_drift, 2)))
            total_score += regime_drift * 0.3
        if risk_drift > 0:
            sources.append(DriftSource(source="risk", contribution=round(risk_drift, 2)))
            total_score += risk_drift * 0.2

        overall = min(100.0, total_score)
        risk_warnings: list[str] = []
        recommended_actions: list[str] = []

        if alloc_drift > 30:
            risk_warnings.append(f"Allocation drift elevated ({alloc_drift:.1f})")
            recommended_actions.append("Reduce allocation update rate")
        if regime_drift > 30:
            risk_warnings.append(f"Regime drift detected ({regime_drift:.1f})")
            recommended_actions.append("Increase regime transition inertia")
        if risk_drift > 30:
            risk_warnings.append(f"Risk structure drift ({risk_drift:.1f})")
            recommended_actions.append("Re-estimate covariance matrix")
        if overall > 50:
            recommended_actions.append("Trigger full portfolio rebalance")
        if not recommended_actions:
            recommended_actions.append("No action required")

        if overall < 20:
            trend = "stable"
        elif overall < 50:
            trend = "watch"
        else:
            trend = "diverging"

        report = PortfolioDriftReport(
            overall_drift_score=round(overall, 2),
            allocation_drift=round(alloc_drift, 2),
            regime_drift=round(regime_drift, 2),
            risk_drift=round(risk_drift, 2),
            drift_sources=sources,
            risk_warnings=risk_warnings,
            recommended_actions=recommended_actions,
            drift_trend=trend,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        self._local_reports.append(report)
        await self._safe_redis("rpush", self.PREFIX, report.model_dump_json())
        if overall > drift_threshold:
            await audit_emit("control.drift.detected", "control", "drift", {
                "score": overall, "sources": [s.source for s in sources],
            })
        return report

    def _compute_allocation_drift(
        self, current: dict[str, float], equilibrium: dict[str, float],
    ) -> float:
        keys = set(current.keys()) | set(equilibrium.keys())
        if not keys:
            return 0.0
        diff_sum = 0.0
        for k in keys:
            c = current.get(k, 0.0)
            e = equilibrium.get(k, 0.0)
            diff_sum += (c - e) ** 2
        return math.sqrt(diff_sum / len(keys)) * 100

    def _compute_regime_drift(
        self, predicted: dict[str, float] | None, realized: dict[str, float] | None,
    ) -> float:
        if not predicted or not realized:
            return 0.0
        keys = set(predicted.keys()) | set(realized.keys())
        diff_sum = 0.0
        for k in keys:
            p = predicted.get(k, 0.0)
            r = realized.get(k, 0.0)
            diff_sum += (p - r) ** 2
        return math.sqrt(diff_sum / len(keys)) * 100

    def _compute_risk_drift(
        self, current: dict[str, dict[str, float]] | None,
        baseline: dict[str, dict[str, float]] | None,
    ) -> float:
        if not current or not baseline:
            return 0.0
        keys = set(current.keys()) & set(baseline.keys())
        if not keys:
            return 0.0
        diffs = 0.0
        count = 0
        for k in keys:
            crow = current.get(k, {})
            brow = baseline.get(k, {})
            inner = set(crow.keys()) & set(brow.keys())
            for j in inner:
                diffs += (crow.get(j, 0.0) - brow.get(j, 0.0)) ** 2
                count += 1
        return math.sqrt(diffs / max(count, 1)) * 100

    async def get_latest(self) -> PortfolioDriftReport | None:
        raw = await self._safe_redis("lrange", self.PREFIX, -1, -1)
        if raw:
            try:
                return PortfolioDriftReport.model_validate_json(raw[0])
            except Exception:
                pass
        return self._local_reports[-1] if self._local_reports else None


portfolio_drift_detector = PortfolioDriftDetector()
