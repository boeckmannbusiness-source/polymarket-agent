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

        status = ReadinessStatus.NOT_STARTED

        if snapshot.decision_count == 0:
            status = ReadinessStatus.NOT_STARTED
        elif snapshot.decision_count < 100: # Arbitrary threshold for COLLECTING
            status = ReadinessStatus.COLLECTING
        elif snapshot.decision_count < 500:
            status = ReadinessStatus.INSUFFICIENT_VOLUME
        else:
            if audit["status"] == "READY":
                status = ReadinessStatus.READY
            else:
                status = ReadinessStatus.EVALUATING

        return {
            "strategy_id": strategy_id,
            "readiness_status": status.value,
            "decision_count": snapshot.decision_count,
            "blocking_reasons": audit["reasons"],
            "data_origin": snapshot.data_origin,
            "snapshot_hash": snapshot.snapshot_hash
        }
