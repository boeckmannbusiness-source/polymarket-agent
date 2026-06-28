import os
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.services.shadow.scorecard_engine import ScorecardEngine
from app.services.shadow.policy_parser import parse_promotion_policy
from app.core.logging import logger

class PromotionAuditService:
    """
    Service for auditing strategies against promotion policies and generating reports.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)

    async def audit_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """
        Audits a specific strategy against the promotion policy.
        """
        scorecard = await self.scorecard_engine.generate_scorecard(strategy_id)
        thresholds = parse_promotion_policy()

        metrics = scorecard.global_metrics

        ready = True
        reasons = []

        # 1. Decision Volume
        min_decisions = thresholds.get("min_decisions", 500)
        if metrics.decision_count < min_decisions:
            ready = False
            reasons.append(f"Insufficient decision volume: {metrics.decision_count} < {min_decisions}")

        # 2. Replay Parity
        min_parity = thresholds.get("min_replay_parity", 0.95)
        if metrics.replay_parity < min_parity:
            ready = False
            reasons.append(f"Replay parity below threshold: {metrics.replay_parity:.2%} < {min_parity:.0%}")

        # 3. Performance (EV)
        if metrics.realized_ev <= 0:
            ready = False
            reasons.append(f"Positive realized EV required: {metrics.realized_ev:.4f}")

        # 4. Confidence Calibration (Brier Score)
        max_brier = thresholds.get("max_brier_score", 0.25)
        if metrics.brier_score > max_brier:
            ready = False
            reasons.append(f"Confidence calibration unstable (Brier Score): {metrics.brier_score:.4f} > {max_brier}")

        # Check for any certification violations
        from sqlalchemy import select
        from app.models.shadow_decision_log import ShadowDecisionLog
        violation_query = select(ShadowDecisionLog).where(
            ShadowDecisionLog.strategy_id == strategy_id,
            ShadowDecisionLog.certification_violation == True
        )
        violation_result = await self.db.execute(violation_query)
        violations = violation_result.scalars().all()
        if violations:
            ready = False
            reasons.append(f"Certification violations detected: {len(violations)}")

        status = "READY" if ready else "NOT_READY"

        return {
            "strategy_id": strategy_id,
            "status": status,
            "reasons": reasons,
            "metrics": metrics.model_dump(),
            "thresholds": thresholds,
            "timestamp": datetime.now().isoformat()
        }

    async def generate_promotion_report(self, strategy_id: str) -> str:
        """
        Generates a markdown promotion report for a strategy.
        """
        audit = await self.audit_strategy(strategy_id)

        report_md = f"""# PROMOTION_REPORT: {strategy_id}
Generated at: {audit['timestamp']}
Status: **{audit['status']}**

## Policy Evaluation
"""
        if audit['reasons']:
            report_md += "### Blocking Reasons\n"
            for r in audit['reasons']:
                report_md += f"- {r}\n"
        else:
            report_md += "All promotion criteria met.\n"

        metrics = audit['metrics']
        thresholds = audit['thresholds']

        report_md += f"""
## Key Metrics
| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Decision Count | {metrics['decision_count']} | {thresholds.get('min_decisions', 500)} | {"PASS" if metrics['decision_count'] >= thresholds.get('min_decisions', 500) else "FAIL"} |
| Replay Parity | {metrics['replay_parity']:.2%} | {thresholds.get('min_replay_parity', 0.95):.0%} | {"PASS" if metrics['replay_parity'] >= thresholds.get('min_replay_parity', 0.95) else "FAIL"} |
| Realized EV | {metrics['realized_ev']:.4f} | > 0.0000 | {"PASS" if metrics['realized_ev'] > 0 else "FAIL"} |
| Brier Score | {metrics['brier_score']:.4f} | ≤ {thresholds.get('max_brier_score', 0.25)} | {"PASS" if metrics['brier_score'] <= thresholds.get('max_brier_score', 0.25) else "FAIL"} |

"""
        # Save to file
        filename = f"PROMOTION_REPORT_{strategy_id}.md"
        with open(filename, "w") as f:
            f.write(report_md)

        return report_md
