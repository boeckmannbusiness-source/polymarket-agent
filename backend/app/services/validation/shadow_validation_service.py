import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog
from app.core.logging import logger


class ShadowValidationService:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._injection_state: dict[str, bool] = {
            "remove_regime_data": False,
            "inject_low_confidence": False,
            "inject_high_drift": False,
            "simulate_redis_outage": False,
            "simulate_valkey_outage": False,
        }
        self._start_time: datetime | None = None

    async def start_run(self, db: AsyncSession):
        self._start_time = datetime.now(timezone.utc)
        self.db = db

    async def _ensure_db(self, db: AsyncSession | None = None) -> AsyncSession:
        return db or self.db

    async def get_decision_logs(
        self,
        db: AsyncSession | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 1000,
    ) -> list[ShadowDecisionLog]:
        session = await self._ensure_db(db)
        query = select(ShadowDecisionLog).order_by(desc(ShadowDecisionLog.timestamp))
        if since:
            query = query.where(ShadowDecisionLog.timestamp >= since)
        if until:
            query = query.where(ShadowDecisionLog.timestamp <= until)
        query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_execution_metrics(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        total_result = await session.execute(select(func.count(ShadowDecisionLog.id)))
        total_decisions = total_result.scalar() or 0

        approved_result = await session.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.safety_gate_decision == "SHADOW_APPROVED"
            )
        )
        approved = approved_result.scalar() or 0

        blocked_result = await session.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.safety_gate_decision == "SHADOW_BLOCKED"
            )
        )
        blocked = blocked_result.scalar() or 0

        return {
            "total_decisions": total_decisions,
            "approved_decisions": approved,
            "blocked_decisions": blocked,
            "approval_ratio": round(approved / total_decisions, 4) if total_decisions > 0 else 0.0,
            "rejection_ratio": round(blocked / total_decisions, 4) if total_decisions > 0 else 0.0,
        }

    async def get_safety_metrics(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        def rejection_pattern_like(pattern: str):
            return select(func.count(ShadowDecisionLog.id)).where(
                and_(
                    ShadowDecisionLog.safety_gate_decision == "SHADOW_BLOCKED",
                    ShadowDecisionLog.rejection_reason.ilike(f"%{pattern}%"),
                )
            )

        high_drift = await session.execute(rejection_pattern_like("DRIFT_SCORE"))
        low_stability = await session.execute(rejection_pattern_like("STABILITY_SCORE"))
        low_confidence = await session.execute(rejection_pattern_like("REGIME_CONFIDENCE"))
        exposure_block = await session.execute(rejection_pattern_like("EXPOSURE"))
        drawdown_block = await session.execute(rejection_pattern_like("DRAWDOWN"))
        control_failure = await session.execute(rejection_pattern_like("CONTROL_FAILURE"))
        kill_switch = await session.execute(rejection_pattern_like("KILL_SWITCH"))

        from app.services.safety.execution_safety_gate import execution_safety_gate
        gate_metrics = execution_safety_gate.get_metrics_snapshot()

        return {
            "high_drift_blocks": high_drift.scalar() or 0,
            "low_stability_blocks": low_stability.scalar() or 0,
            "low_confidence_blocks": low_confidence.scalar() or 0,
            "exposure_limit_blocks": exposure_block.scalar() or 0,
            "drawdown_limit_blocks": drawdown_block.scalar() or 0,
            "control_failure_blocks": control_failure.scalar() or 0,
            "kill_switch_activations": kill_switch.scalar() or 0,
            "gate_metrics": gate_metrics,
        }

    async def get_regime_metrics(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        result = await session.execute(
            select(
                ShadowDecisionLog.regime,
                func.count(ShadowDecisionLog.id).label("count"),
            )
            .where(ShadowDecisionLog.regime != "")
            .group_by(ShadowDecisionLog.regime)
            .order_by(desc("count"))
        )
        regime_counts = {row[0]: row[1] for row in result.all()}

        result = await session.execute(
            select(
                ShadowDecisionLog.regime,
                func.avg(ShadowDecisionLog.regime_confidence).label("avg_confidence"),
            )
            .where(
                and_(
                    ShadowDecisionLog.regime != "",
                    ShadowDecisionLog.regime_confidence.isnot(None),
                )
            )
            .group_by(ShadowDecisionLog.regime)
        )
        regime_confidence = {row[0]: round(float(row[1]), 4) for row in result.all()}

        return {
            "regime_distribution": regime_counts,
            "regime_avg_confidence": regime_confidence,
            "regime_transition_count": len(regime_counts),
        }

    async def get_optimization_metrics(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        result = await session.execute(
            select(
                func.avg(ShadowDecisionLog.optimization_weight).label("avg_weight"),
                func.min(ShadowDecisionLog.optimization_weight).label("min_weight"),
                func.max(ShadowDecisionLog.optimization_weight).label("max_weight"),
            )
            .where(ShadowDecisionLog.optimization_weight.isnot(None))
        )
        row = result.one()
        avg_weight = float(row.avg_weight) if row.avg_weight else 0.0
        min_weight = float(row.min_weight) if row.min_weight else 0.0
        max_weight = float(row.max_weight) if row.max_weight else 0.0

        result = await session.execute(
            select(
                func.avg(ShadowDecisionLog.stability_score).label("avg_stability"),
                func.avg(ShadowDecisionLog.drift_score).label("avg_drift"),
                func.avg(ShadowDecisionLog.exposure_level).label("avg_exposure"),
            )
        )
        row = result.one()
        avg_stability = float(row.avg_stability) if row.avg_stability else 0.0
        avg_drift = float(row.avg_drift) if row.avg_drift else 0.0
        avg_exposure = float(row.avg_exposure) if row.avg_exposure else 0.0

        return {
            "avg_optimization_weight": round(avg_weight, 4),
            "min_optimization_weight": round(min_weight, 4),
            "max_optimization_weight": round(max_weight, 4),
            "avg_stability_score": round(avg_stability, 2),
            "avg_drift_score": round(avg_drift, 2),
            "avg_exposure_level": round(avg_exposure, 4),
            "concentration_score": round(max_weight, 4) if max_weight > 0 else 0.0,
            "diversification_score": round(1.0 - (max_weight - min_weight), 4) if max_weight > 0 and min_weight >= 0 else 0.0,
        }

    async def get_control_layer_metrics(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
            .where(ShadowDecisionLog.rejection_reason.ilike("%CONTROL_FAILURE%"))
        )
        control_interventions = result.scalar() or 0

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
            .where(ShadowDecisionLog.rejection_reason.ilike("%DRIFT_SCORE%"))
        )
        drift_events = result.scalar() or 0

        return {
            "control_layer_interventions": control_interventions,
            "drift_events": drift_events,
            "feedback_dampening_events": 0,
            "allocation_smoothing_events": 0,
        }

    async def get_failure_injection_status(self) -> dict[str, Any]:
        return dict(self._injection_state)

    def set_injection_state(self, test_name: str, active: bool):
        if test_name in self._injection_state:
            self._injection_state[test_name] = active

    async def check_logging_completeness(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
        )
        total = result.scalar() or 0

        if total == 0:
            return {"completeness_pct": 0.0, "total_entries": 0, "missing_fields": []}

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
            .where(ShadowDecisionLog.safety_gate_decision.is_(None))
        )
        missing_decision = result.scalar() or 0

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
            .where(ShadowDecisionLog.market_id.is_(None))
        )
        missing_market = result.scalar() or 0

        result = await session.execute(
            select(func.count(ShadowDecisionLog.id))
            .where(ShadowDecisionLog.strategy_id.is_(None))
        )
        missing_strategy = result.scalar() or 0

        missing = sum([missing_decision, missing_market, missing_strategy])
        completeness = round((1.0 - missing / (total * 3)) * 100, 2) if total > 0 else 0.0

        missing_fields = []
        if missing_decision:
            missing_fields.append("safety_gate_decision")
        if missing_market:
            missing_fields.append("market_id")
        if missing_strategy:
            missing_fields.append("strategy_id")

        return {
            "completeness_pct": completeness,
            "total_entries": total,
            "missing_fields": missing_fields,
        }

    async def generate_report(self, db: AsyncSession | None = None) -> dict[str, Any]:
        session = await self._ensure_db(db)

        runtime_hours = 0.0
        if self._start_time:
            runtime_hours = (datetime.now(timezone.utc) - self._start_time).total_seconds() / 3600

        execution_metrics = await self.get_execution_metrics(session)
        safety_metrics = await self.get_safety_metrics(session)
        regime_metrics = await self.get_regime_metrics(session)
        optimization_metrics = await self.get_optimization_metrics(session)
        control_metrics = await self.get_control_layer_metrics(session)
        completeness = await self.check_logging_completeness(session)

        total_safety_events = sum(
            safety_metrics.get(k, 0) for k in [
                "high_drift_blocks", "low_stability_blocks", "low_confidence_blocks",
                "exposure_limit_blocks", "drawdown_limit_blocks", "control_failure_blocks",
                "kill_switch_activations",
            ]
        )

        success = all([
            completeness["completeness_pct"] > 95.0,
            execution_metrics["total_decisions"] > 0,
            execution_metrics["approved_decisions"] + execution_metrics["blocked_decisions"] > 0,
        ])

        recommendation = "NOT_READY"
        if success and runtime_hours >= 48:
            recommendation = "MICRO_CAPITAL_READY"
        elif success and runtime_hours >= 24:
            recommendation = "EXTEND_SHADOW_TEST"
        elif runtime_hours < 48:
            recommendation = "EXTEND_SHADOW_TEST"

        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime_summary": {
                "start_time": self._start_time.isoformat() if self._start_time else "",
                "runtime_hours": round(runtime_hours, 2),
                "minimum_required_hours": 48,
                "preferred_hours": 72,
                "status": "RUNNING" if runtime_hours < 48 else "COMPLETE",
            },
            "execution_metrics": execution_metrics,
            "safety_metrics": safety_metrics,
            "regime_analysis": regime_metrics,
            "optimization_analysis": optimization_metrics,
            "control_layer_analysis": control_metrics,
            "failure_injection_results": dict(self._injection_state),
            "logging_quality": completeness,
            "known_issues": [],
            "success_criteria_met": success,
            "recommendation": recommendation,
        }


shadow_validation_service = ShadowValidationService()
