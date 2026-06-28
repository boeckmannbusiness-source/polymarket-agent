import hashlib
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.shadow_decision_log import ShadowDecisionLog
from app.schemas.shadow import PromotionEvidenceSnapshot
from app.services.shadow.scorecard_engine import ScorecardEngine
from app.core.logging import logger

class EvidenceEngine:
    """
    Engine for generating immutable promotion evidence snapshots.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)

    async def generate_snapshot(self, strategy_id: Optional[str] = None) -> PromotionEvidenceSnapshot:
        """
        Generates a single consistent evidence snapshot for a strategy or global.
        """
        scorecard = await self.scorecard_engine.generate_scorecard(strategy_id)
        metrics = scorecard.global_metrics

        # Count certification violations explicitly
        from app.models.shadow_decision_log import ShadowDecisionLog
        cert_query = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.certification_violation == True)
        if strategy_id and strategy_id != "GLOBAL":
            cert_query = cert_query.where(ShadowDecisionLog.strategy_id == strategy_id)

        cert_res = await self.db.execute(cert_query)
        cert_violations = cert_res.scalar() or 0

        # Determine data origin
        data_origin = "synthetic"

        # Check if we have ANY decisions in the DB (real or unresolved)
        from app.models.shadow_decision_log import ShadowDecisionLog
        count_query = select(func.count(ShadowDecisionLog.id))
        if strategy_id and strategy_id != "GLOBAL":
            count_query = count_query.where(ShadowDecisionLog.strategy_id == strategy_id)

        count_res = await self.db.execute(count_query)
        total_in_db = count_res.scalar() or 0

        if total_in_db > 0:
            # If we have decisions, check if they are real shadow decisions
            # For Sprint 8.3, we assume if they are in the DB they are real shadow data
            # unless explicitly marked otherwise (e.g. in tests)
            data_origin = "shadow"

        snapshot = PromotionEvidenceSnapshot(
            strategy_id=strategy_id or "GLOBAL",
            decision_count=metrics.decision_count,
            replay_parity=metrics.replay_parity,
            realized_ev=metrics.realized_ev,
            brier_score=metrics.brier_score,
            certification_violations=cert_violations,
            data_origin=data_origin,
            timestamp=datetime.now()
        )

        # Calculate snapshot hash for immutability check
        snapshot_data = snapshot.model_dump(exclude={"snapshot_hash", "timestamp"})
        snapshot_str = json.dumps(snapshot_data, sort_keys=True)
        snapshot.snapshot_hash = hashlib.sha256(snapshot_str.encode()).hexdigest()

        return snapshot
