from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shadow.scorecard_engine import ScorecardEngine
from app.schemas.shadow import StabilityReceipt, StrategyScorecard
from app.core.logging import logger

class StrategyStabilityMonitor:
    """
    Monitors strategies for stability issues like EV collapse or confidence drift.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)

    async def check_stability(self, strategy_id: str) -> List[StabilityReceipt]:
        """
        Runs stability checks on a strategy and returns receipts for any detected issues.
        """
        scorecard = await self.scorecard_engine.generate_scorecard(strategy_id)
        receipts = []

        # 1. EV Collapse (Recent EV significantly lower than global EV)
        receipts.extend(self._check_ev_collapse(scorecard))

        # 2. Confidence Drift (High variance in recent confidence scores)
        receipts.extend(self._check_confidence_drift(scorecard))

        # 3. Replay Degradation (Recent parity lower than global)
        receipts.extend(self._check_replay_degradation(scorecard))

        # 4. Variance Spikes (Detected via confidence_drift in ScorecardMetrics)
        # (This is already covered by confidence_drift check above, but could be specialized)

        return receipts

    def _check_ev_collapse(self, scorecard: StrategyScorecard) -> List[StabilityReceipt]:
        receipts = []
        global_ev = scorecard.global_metrics.realized_ev / (scorecard.global_metrics.decision_count or 1)
        recent_ev = scorecard.rolling_7d.realized_ev / (scorecard.rolling_7d.decision_count or 1)

        if scorecard.rolling_7d.decision_count >= 5:
            if recent_ev < global_ev * 0.5 or (global_ev > 0 and recent_ev < 0):
                severity = "HIGH" if recent_ev < 0 else "MEDIUM"
                receipts.append(StabilityReceipt(
                    strategy_id=scorecard.strategy_id,
                    severity=severity,
                    metric="realized_ev",
                    message=f"EV Collapse detected: Recent EV ({recent_ev:.4f}) significantly lower than Global EV ({global_ev:.4f})",
                    evidence={"global_ev": global_ev, "recent_ev": recent_ev}
                ))
        return receipts

    def _check_confidence_drift(self, scorecard: StrategyScorecard) -> List[StabilityReceipt]:
        receipts = []
        drift = scorecard.rolling_7d.confidence_drift
        if drift > 0.3: # Threshold for high variance
            receipts.append(StabilityReceipt(
                strategy_id=scorecard.strategy_id,
                severity="MEDIUM",
                metric="confidence_drift",
                message=f"High confidence drift detected: {drift:.4f}",
                evidence={"confidence_drift": drift}
            ))
        return receipts

    def _check_replay_degradation(self, scorecard: StrategyScorecard) -> List[StabilityReceipt]:
        receipts = []
        global_parity = scorecard.global_metrics.replay_parity
        recent_parity = scorecard.rolling_7d.replay_parity

        if scorecard.rolling_7d.decision_count >= 5:
            if recent_parity < global_parity - 0.1:
                receipts.append(StabilityReceipt(
                    strategy_id=scorecard.strategy_id,
                    severity="HIGH",
                    metric="replay_parity",
                    message=f"Replay degradation detected: Recent parity ({recent_parity:.2%}) dropped below Global parity ({global_parity:.2%})",
                    evidence={"global_parity": global_parity, "recent_parity": recent_parity}
                ))
        return receipts
