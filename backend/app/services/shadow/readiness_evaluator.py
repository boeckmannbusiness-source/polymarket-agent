from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.outcome_evaluator import OutcomeEvaluator
from app.core.logging import logger

class PromotionReadinessEvaluator:
    """
    Evaluates strategy readiness for Sandbox promotion based on policy thresholds.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.evaluator = OutcomeEvaluator(db)

    async def evaluate_readiness(self, strategy_id: str) -> Dict[str, Any]:
        """
        Evaluate if a strategy is ready for Sandbox promotion.
        Ensures READY status only if ALL policy requirements pass.
        """
        metrics = await self.evaluator.evaluate_strategy(strategy_id)

        # Pull global metrics for parity check
        global_metrics = await self.evaluator.get_global_metrics()

        # Policy Thresholds (parsed from SANDBOX_PROMOTION_POLICY.md)
        from app.services.shadow.policy_parser import parse_promotion_policy
        thresholds = parse_promotion_policy()

        MIN_DECISIONS = thresholds.get("min_decisions", 500)
        MIN_REPLAY_PARITY = thresholds.get("min_replay_parity", 0.95)
        MAX_BRIER_SCORE = thresholds.get("max_brier_score", 0.25)

        blocking_reasons = []

        # 1. Decision Volume
        if metrics["total_decisions"] < MIN_DECISIONS:
            blocking_reasons.append(f"Insufficient decision volume: {metrics['total_decisions']} < {MIN_DECISIONS}")

        # 2. Replay Parity
        replay_parity = global_metrics.get("replay_parity", 0.0)
        if replay_parity < MIN_REPLAY_PARITY:
            blocking_reasons.append(f"Replay parity too low: {replay_parity:.2%} < {MIN_REPLAY_PARITY:.0%}")

        # 3. Performance (EV)
        if metrics["realized_ev"] <= 0:
            blocking_reasons.append(f"Positive realized EV required: {metrics['realized_ev']:.4f}")

        # 4. Certification Integrity
        cert_violations = global_metrics.get("certification_violations", 0)
        if cert_violations > 0:
            blocking_reasons.append(f"Certification violations detected: {cert_violations}")

        # 5. Confidence Calibration
        brier = metrics.get("brier_score", 1.0)
        if brier > MAX_BRIER_SCORE:
            blocking_reasons.append(f"Confidence calibration unstable (Brier Score): {brier:.4f} > {MAX_BRIER_SCORE}")

        # Explicit status aggregation
        status = "READY" if not blocking_reasons else "NOT_READY"

        return {
            "status": status,
            "strategy_id": strategy_id,
            "blocking_reasons": blocking_reasons,
            "progress": {
                "decision_volume": f"{metrics['total_decisions']}/{MIN_DECISIONS}",
                "replay_parity": f"{replay_parity:.2%}",
                "ev": f"{metrics['realized_ev']:.4f}",
                "calibration": f"{brier:.4f}"
            }
        }
