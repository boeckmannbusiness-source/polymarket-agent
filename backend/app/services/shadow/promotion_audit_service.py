import os
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.services.shadow.scorecard_engine import ScorecardEngine
from app.services.shadow.policy_parser import parse_promotion_policy
from app.services.shadow.evidence_engine import EvidenceEngine
from app.schemas.shadow import PromotionEvidenceSnapshot
from app.core.logging import logger

class PromotionAuditService:
    """
    Service for auditing strategies against promotion policies and generating reports.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)
        self.evidence_engine = EvidenceEngine(db)

    async def audit_strategy(self, strategy_id: str, snapshot: Optional[PromotionEvidenceSnapshot] = None) -> Dict[str, Any]:
        """
        Audits a specific strategy against the promotion policy using a snapshot.
        """
        if snapshot is None:
            snapshot = await self.evidence_engine.generate_snapshot(strategy_id)

        thresholds = parse_promotion_policy()

        blocking_reasons = []

        # 1. Decision Volume
        min_decisions = thresholds.get("min_decisions", 500)
        if snapshot.decision_count < min_decisions:
            blocking_reasons.append(f"Insufficient decision volume: {snapshot.decision_count} < {min_decisions}")

        # 2. Replay Parity
        min_parity = thresholds.get("min_replay_parity", 0.95)
        if snapshot.replay_parity < min_parity:
            blocking_reasons.append(f"Replay parity below threshold: {snapshot.replay_parity:.2%} < {min_parity:.0%}")

        # 3. Performance (EV)
        if snapshot.realized_ev <= 0:
            blocking_reasons.append(f"Positive realized EV required: {snapshot.realized_ev:.4f}")

        # 4. Confidence Calibration (Brier Score)
        max_brier = thresholds.get("max_brier_score", 0.25)
        if snapshot.brier_score > max_brier:
            blocking_reasons.append(f"Confidence calibration unstable (Brier Score): {snapshot.brier_score:.4f} > {max_brier}")

        # 5. Certification Integrity
        if snapshot.certification_violations > 0:
            blocking_reasons.append(f"Certification violations detected: {snapshot.certification_violations}")

        # 6. Evidence Origin Enforcement (Sprint 8.4A Integrity)
        # IF origin != shadow: READY impossible
        if snapshot.data_origin != "shadow":
            blocking_reasons.append(f"Promotion requires real shadow evidence: current origin is {snapshot.data_origin}")

        if snapshot.data_origin in ["synthetic", "mixed"]:
            blocking_reasons.append(f"Origin '{snapshot.data_origin}' is strictly rejected for READY status.")

        # Explicit status aggregation
        # IF origin != shadow: status can never be READY
        if snapshot.data_origin != "shadow":
            status = "NOT_READY"
        else:
            status = "READY" if not blocking_reasons else "NOT_READY"

        return {
            "strategy_id": strategy_id,
            "status": status,
            "reasons": blocking_reasons,
            "metrics": snapshot.model_dump(),
            "thresholds": thresholds,
            "timestamp": snapshot.timestamp.isoformat() if hasattr(snapshot.timestamp, 'isoformat') else str(snapshot.timestamp),
            "snapshot_hash": snapshot.snapshot_hash
        }

    async def generate_promotion_report(self, strategy_id: str, snapshot: Optional[PromotionEvidenceSnapshot] = None) -> str:
        """
        Generates a markdown promotion report for a strategy using a snapshot.
        """
        audit = await self.audit_strategy(strategy_id, snapshot=snapshot)

        report_md = f"""# PROMOTION_REPORT: {strategy_id}
Generated at: {audit['timestamp']}
Snapshot Hash: {audit['snapshot_hash']}
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

        def fmt_metric(val: float, fmt: str, count: int) -> str:
            if count == 0:
                return "NOT_AVAILABLE"
            if fmt == "pct":
                return f"{val:.2%}"
            return f"{val:.4f}"

        report_md += f"""
## Key Metrics
| Metric | Value | Threshold | Result |
|--------|-------|-----------|--------|
| Resolved Decision Count | {metrics['decision_count']} | {thresholds.get('min_decisions', 500)} | {"PASS" if metrics['decision_count'] >= thresholds.get('min_decisions', 500) else "FAIL"} |
| Replay Parity | {fmt_metric(metrics['replay_parity'], "pct", metrics['decision_count'])} | {thresholds.get('min_replay_parity', 0.95):.0%} | {"PASS" if metrics['decision_count'] > 0 and metrics['replay_parity'] >= thresholds.get('min_replay_parity', 0.95) else "FAIL"} |
| Realized EV | {fmt_metric(metrics['realized_ev'], "num", metrics['decision_count'])} | > 0.0000 | {"PASS" if metrics['decision_count'] > 0 and metrics['realized_ev'] > 0 else "FAIL"} |
| Brier Score | {fmt_metric(metrics['brier_score'], "num", metrics['decision_count'])} | ≤ {thresholds.get('max_brier_score', 0.25)} | {"PASS" if metrics['decision_count'] > 0 and metrics['brier_score'] <= thresholds.get('max_brier_score', 0.25) else "FAIL"} |
| Data Origin | {metrics['data_origin']} | shadow | {"PASS" if metrics['data_origin'] == "shadow" else "FAIL"} |

"""
        # Save to file
        filename = f"PROMOTION_REPORT_{strategy_id}.md"
        with open(filename, "w") as f:
            f.write(report_md)

        return report_md
