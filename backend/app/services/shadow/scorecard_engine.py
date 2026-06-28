from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, literal_column

from app.models.shadow_decision_log import ShadowDecisionLog
from app.schemas.shadow import StrategyScorecard, ScorecardMetrics
from app.core.logging import logger

class ScorecardEngine:
    """
    Engine for generating strategy scorecards based on shadow decision history.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_scorecard(self, strategy_id: Optional[str] = None) -> StrategyScorecard:
        """
        Generates a full scorecard for a specific strategy or global metrics if strategy_id is None.
        """
        global_metrics = await self._compute_metrics(strategy_id)
        rolling_7d = await self._compute_metrics(strategy_id, days=7)
        rolling_30d = await self._compute_metrics(strategy_id, days=30)

        return StrategyScorecard(
            strategy_id=strategy_id or "GLOBAL",
            global_metrics=global_metrics,
            rolling_7d=rolling_7d,
            rolling_30d=rolling_30d,
            generated_at=datetime.now()
        )

    async def _compute_metrics(self, strategy_id: Optional[str] = None, days: Optional[int] = None) -> ScorecardMetrics:
        """
        Computes scorecard metrics for a given strategy (or all) and time window using SQL aggregates.
        """
        # Base filters
        filters = []
        if strategy_id:
            filters.append(ShadowDecisionLog.strategy_id == strategy_id)
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            filters.append(ShadowDecisionLog.timestamp >= cutoff)

        # Win condition logic (shared across aggregates)
        is_win_cond = case(
            (ShadowDecisionLog.actual_ev.isnot(None), ShadowDecisionLog.actual_ev > 0),
            (ShadowDecisionLog.simulated_entry_price.isnot(None) & ShadowDecisionLog.simulated_exit_price.isnot(None),
                case(
                    (ShadowDecisionLog.decision == "buy", ShadowDecisionLog.simulated_exit_price > ShadowDecisionLog.simulated_entry_price),
                    (ShadowDecisionLog.decision == "sell", ShadowDecisionLog.simulated_exit_price < ShadowDecisionLog.simulated_entry_price),
                    else_=False
                )
            ),
            else_=False
        )

        # Build Aggregate Query
        query = select(
            func.count(ShadowDecisionLog.id).label("total_decisions"),
            func.sum(case((ShadowDecisionLog.simulated_exit_price.isnot(None), 1), else_=0)).label("total_closed"),
            func.sum(ShadowDecisionLog.actual_ev).label("sum_realized_ev"),
            func.sum(ShadowDecisionLog.expected_ev).label("sum_expected_ev"),
            func.sum(case((is_win_cond, 1), else_=0)).label("win_count"),
            func.sum(case((ShadowDecisionLog.replay_match == True, 1), else_=0)).label("replay_matches"),
            func.sum(case((ShadowDecisionLog.governor_decision == "BLOCK", 1), else_=0)).label("rejected_count"),
            # Brier Score components: (confidence - outcome)^2
            func.sum(
                case(
                    (ShadowDecisionLog.simulated_exit_price.isnot(None),
                        func.pow(ShadowDecisionLog.confidence - case((is_win_cond, 1.0), else_=0.0), 2)
                    ),
                    else_=0
                )
            ).label("sum_brier_err"),
            # Calibration Error components: |confidence - outcome|
            func.sum(
                case(
                    (ShadowDecisionLog.simulated_exit_price.isnot(None),
                        func.abs(ShadowDecisionLog.confidence - case((is_win_cond, 1.0), else_=0.0))
                    ),
                    else_=0
                )
            ).label("sum_cal_err"),
            # For Confidence Drift
            func.avg(ShadowDecisionLog.confidence).label("avg_confidence"),
            func.count(ShadowDecisionLog.confidence).label("conf_count")
        ).where(*filters)

        result = await self.db.execute(query)
        row = result.fetchone()

        if not row or row.total_decisions == 0:
            return ScorecardMetrics()

        total_decisions = row.total_decisions
        total_closed = row.total_closed or 0
        sum_realized_ev = row.sum_realized_ev or 0.0
        sum_expected_ev = row.sum_expected_ev or 0.0
        win_count = row.win_count or 0
        replay_matches = row.replay_matches or 0
        rejected_count = row.rejected_count or 0
        sum_brier_err = row.sum_brier_err or 0.0
        sum_cal_err = row.sum_cal_err or 0.0

        win_rate = win_count / total_closed if total_closed > 0 else 0.0
        brier_score = sum_brier_err / total_closed if total_closed > 0 else 1.0
        calibration_error = sum_cal_err / total_closed if total_closed > 0 else 0.0
        replay_parity = replay_matches / total_decisions if total_decisions > 0 else 0.0
        rejection_rate = rejected_count / total_decisions if total_decisions > 0 else 0.0
        alpha = (sum_realized_ev - sum_expected_ev) / total_decisions if total_decisions > 0 else 0.0

        # Confidence Drift (simplified via another query if needed, or approx)
        # For precision, let's do a sub-query for variance if conf_count > 1
        confidence_drift = 0.0
        if row.conf_count and row.conf_count > 1:
            var_query = select(func.variance(ShadowDecisionLog.confidence)).where(*filters)
            var_res = await self.db.execute(var_query)
            variance = var_res.scalar() or 0.0
            confidence_drift = variance ** 0.5

        return ScorecardMetrics(
            decision_count=total_decisions,
            realized_ev=sum_realized_ev,
            expected_ev=sum_expected_ev,
            alpha=alpha,
            win_rate=win_rate,
            brier_score=brier_score,
            replay_parity=replay_parity,
            rejection_rate=rejection_rate,
            calibration_error=calibration_error,
            confidence_drift=confidence_drift
        )
