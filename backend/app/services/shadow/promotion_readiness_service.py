import enum
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.evidence_engine import EvidenceEngine
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.core.logging import logger

class ReadinessStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    COLLECTING = "COLLECTING"
    INSUFFICIENT_VOLUME = "INSUFFICIENT_VOLUME"
    EVALUATING = "EVALUATING"
    READY = "READY"

class PromotionReadinessService:
    """
    Service for determining strategy promotion readiness state.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.evidence_engine = EvidenceEngine(db)
        self.audit_service = PromotionAuditService(db)

    async def get_readiness_state(self, strategy_id: str) -> Dict[str, Any]:
        """
        Determines the current readiness state for a strategy.
        """
        snapshot = await self.evidence_engine.generate_snapshot(strategy_id)
        audit = await self.audit_service.audit_strategy(strategy_id, snapshot=snapshot)

        # Check for awaiting resolution
        total_in_db_query = select(func.count(ShadowDecisionLog.id))
        if strategy_id and strategy_id != "GLOBAL":
            total_in_db_query = total_in_db_query.where(ShadowDecisionLog.strategy_id == strategy_id)

        total_in_db_res = await self.db.execute(total_in_db_query)
        total_in_db = total_in_db_res.scalar() or 0

        status = ReadinessStatus.NOT_STARTED
        reason = "NO_DECISIONS"

        if total_in_db == 0:
            status = ReadinessStatus.NOT_STARTED
            reason = "NO_DECISIONS"
        elif snapshot.decision_count == 0:
            status = ReadinessStatus.COLLECTING
            reason = "AWAITING_RESOLUTION"
        elif snapshot.decision_count < 100: # Arbitrary threshold for COLLECTING
            status = ReadinessStatus.COLLECTING
            reason = "INSUFFICIENT_VOLUME"
        elif snapshot.decision_count < 500:
            status = ReadinessStatus.INSUFFICIENT_VOLUME
            reason = "INSUFFICIENT_VOLUME"
        else:
            if audit["status"] == "READY":
                status = ReadinessStatus.READY
                reason = "READY"
            else:
                status = ReadinessStatus.EVALUATING
                reason = "FAILED_POLICY"

        # Task 4: Forecast logic
        resolved_today = 0
        rolling_7d = 0.0
        eta_days = "UNKNOWN"

        try:
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            seven_days_ago = today_start - timedelta(days=7)

            today_query = select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "RESOLVED",
                ShadowDecisionLog.outcome_timestamp >= today_start
            )
            if strategy_id and strategy_id != "GLOBAL":
                today_query = today_query.where(ShadowDecisionLog.strategy_id == strategy_id)

            today_res = await self.db.execute(today_query)
            resolved_today = today_res.scalar() or 0

            seven_day_query = select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "RESOLVED",
                ShadowDecisionLog.outcome_timestamp >= seven_days_ago
            )
            if strategy_id and strategy_id != "GLOBAL":
                seven_day_query = seven_day_query.where(ShadowDecisionLog.strategy_id == strategy_id)

            seven_day_res = await self.db.execute(seven_day_query)
            seven_day_count = seven_day_res.scalar() or 0
            rolling_7d = seven_day_count / 7.0

            if rolling_7d > 0:
                remaining = 500 - snapshot.decision_count
                if remaining <= 0:
                    eta_days = 0
                else:
                    eta_days = round(remaining / rolling_7d, 1)
        except Exception as e:
            logger.error("forecast_calculation_failed", error=str(e))

        return {
            "strategy_id": strategy_id,
            "readiness_status": status.value,
            "readiness_reason": reason,
            "decision_count": snapshot.decision_count,
            "blocking_reasons": audit["reasons"],
            "data_origin": snapshot.data_origin,
            "snapshot_hash": snapshot.snapshot_hash,
            "forecast": {
                "resolved_today": resolved_today,
                "rolling_7d": rolling_7d,
                "estimated_days_to_500": eta_days
            }
        }
