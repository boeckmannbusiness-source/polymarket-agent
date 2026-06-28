import math
from typing import Any, Optional
from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shadow_decision_log import ShadowDecisionLog
from app.core.logging import logger

class OutcomeEvaluator:
    """
    Decision Outcome Evaluator
    Evaluates the quality and performance of shadow decisions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate_strategy(self, strategy_id: str) -> dict[str, Any]:
        """
        Evaluates performance metrics for a specific strategy.
        """
        result = await self.db.execute(
            select(ShadowDecisionLog).where(
                ShadowDecisionLog.strategy_id == strategy_id,
                ShadowDecisionLog.simulated_exit_price.isnot(None)
            )
        )
        decisions = list(result.scalars().all())

        if not decisions:
            return {
                "strategy_id": strategy_id,
                "total_decisions": 0,
                "message": "No closed decisions found for strategy."
            }

        total_count = len(decisions)
        win_count = 0
        realized_ev = 0.0
        total_confidence_error = 0.0
        total_prediction_error = 0.0

        # Calibration bins: 0.0-0.1, 0.1-0.2, ..., 0.9-1.0
        bins = [0] * 10
        bin_wins = [0] * 10

        pnls = []

        for d in decisions:
            # Simple win/loss based on actual EV or price movement
            if d.actual_ev is not None:
                is_win = d.actual_ev > 0
            else:
                # Fallback: win/loss based on price movement and direction
                entry = d.simulated_entry_price or 0.0
                exit = d.simulated_exit_price or 0.0
                if d.decision == "buy":
                    is_win = exit > entry
                elif d.decision == "sell":
                    is_win = exit < entry
                else:
                    is_win = False

            if is_win:
                win_count += 1

            realized_ev += d.actual_ev if d.actual_ev is not None else 0.0

            # Confidence error (Brier Score component: (confidence - outcome)^2)
            outcome_val = 1.0 if is_win else 0.0
            confidence = d.confidence or 0.0
            total_confidence_error += (confidence - outcome_val) ** 2
            total_prediction_error += abs(confidence - outcome_val)

            # Calibration
            bin_idx = min(int(d.confidence * 10), 9)
            bins[bin_idx] += 1
            if is_win:
                bin_wins[bin_idx] += 1

            if d.actual_ev is not None:
                pnls.append(d.actual_ev)

        win_rate = win_count / total_count
        avg_confidence_error = total_confidence_error / total_count
        brier_score = avg_confidence_error
        overconfidence_index = (sum(d.confidence for d in decisions if d.confidence is not None) / total_count) - win_rate

        # Calibration curve
        calibration_curve = []
        for i in range(10):
            if bins[i] > 0:
                calibration_curve.append({
                    "bin": f"{i/10}-{(i+1)/10}",
                    "count": bins[i],
                    "actual_win_rate": bin_wins[i] / bins[i]
                })

        # Drawdown calculation
        max_drawdown = 0.0
        if pnls:
            peak = 0.0
            current_equity = 0.0
            for pnl in pnls:
                current_equity += pnl
                if current_equity > peak:
                    peak = current_equity
                dd = peak - current_equity
                if dd > max_drawdown:
                    max_drawdown = dd

        return {
            "strategy_id": strategy_id,
            "total_decisions": total_count,
            "win_rate": win_rate,
            "realized_ev": realized_ev,
            "avg_ev": realized_ev / total_count,
            "max_drawdown": max_drawdown,
            "confidence_error": avg_confidence_error, # Lower is better (Brier Score)
            "brier_score": brier_score,
            "overconfidence_index": overconfidence_index,
            "avg_prediction_error": total_prediction_error / total_count,
            "calibration_curve": calibration_curve,
            "prediction_accuracy": win_rate # Simple accuracy for now
        }

    async def get_global_metrics(self) -> dict[str, Any]:
        """
        Aggregates metrics across all strategies.
        """
        result = await self.db.execute(
            select(ShadowDecisionLog).where(
                ShadowDecisionLog.simulated_exit_price.isnot(None)
            )
        )
        decisions = list(result.scalars().all())

        if not decisions:
            return {"total_decisions": 0}

        total_count = len(decisions)
        win_count = 0
        for d in decisions:
            if d.actual_ev is not None:
                if d.actual_ev > 0:
                    win_count += 1
            else:
                entry = d.simulated_entry_price or 0.0
                exit = d.simulated_exit_price or 0.0
                if d.decision == "buy" and exit > entry:
                    win_count += 1
                elif d.decision == "sell" and exit < entry:
                    win_count += 1

        total_ev = sum(d.actual_ev for d in decisions if d.actual_ev is not None)

        replay_matches = sum(1 for d in decisions if d.replay_match is True)
        replay_parity = replay_matches / total_count if total_count > 0 else 0.0

        cert_violations = sum(1 for d in decisions if d.certification_violation is True)

        return {
            "total_decisions": total_count,
            "global_win_rate": win_count / total_count,
            "total_ev": total_ev,
            "avg_ev": total_ev / total_count,
            "replay_parity": replay_parity,
            "certification_violations": cert_violations
        }
