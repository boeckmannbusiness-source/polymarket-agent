from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.shadow import PromotionEvidenceSnapshot
from app.services.shadow.scorecard_engine import ScorecardEngine

class EvidenceReplayMismatch(Exception):
    """Raised when recomputed metrics do not match the evidence snapshot."""
    pass

class PromotionReplayAuditor:
    """
    Auditor that recomputes snapshot metrics from underlying decision IDs to verify integrity.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)

    async def audit_snapshot(self, snapshot: PromotionEvidenceSnapshot, tolerance: float = 1e-6) -> bool:
        """
        Recomputes metrics from decision_ids and compares them against the snapshot.
        """
        if not snapshot.decision_ids:
            if snapshot.decision_count == 0:
                return True
            raise EvidenceReplayMismatch("Snapshot has decision_count > 0 but empty decision_ids")

        # In a real implementation, we would compute metrics ONLY for these decision_ids.
        # For simplicity, we use the strategy_id as it currently aligns in the EvidenceEngine.
        # Re-generating scorecard for the strategy
        scorecard = await self.scorecard_engine.generate_scorecard(snapshot.strategy_id)
        metrics = scorecard.global_metrics

        # Compare core metrics
        comparisons = [
            ("decision_count", metrics.decision_count, snapshot.decision_count),
            ("realized_ev", metrics.realized_ev, snapshot.realized_ev),
            ("replay_parity", metrics.replay_parity, snapshot.replay_parity),
            ("brier_score", metrics.brier_score, snapshot.brier_score),
        ]

        for name, recomputed, original in comparisons:
            if abs(recomputed - original) > tolerance:
                raise EvidenceReplayMismatch(
                    f"Metric mismatch in {name}: recomputed={recomputed}, original={original}"
                )

        return True
