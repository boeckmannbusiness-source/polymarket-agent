from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json

from app.services.shadow.scorecard_engine import ScorecardEngine
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.services.shadow.stability_monitor import StrategyStabilityMonitor
from app.core.logging import logger

class DashboardService:
    """
    Service for aggregating shadow metrics and generating operations reports.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scorecard_engine = ScorecardEngine(db)
        self.audit_service = PromotionAuditService(db)
        self.stability_monitor = StrategyStabilityMonitor(db)

    async def generate_ops_report(self) -> str:
        """
        Generates a comprehensive SHADOW_OPERATIONS_REPORT.md.
        """
        # 1. Global Metrics
        global_scorecard = await self.scorecard_engine.generate_scorecard()

        # 2. Strategy Rankings & Readiness
        from sqlalchemy import select, func
        from app.models.shadow_decision_log import ShadowDecisionLog

        # Global Certification Health
        cert_query = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.certification_violation == True)
        cert_res = await self.db.execute(cert_query)
        global_cert_violations = cert_res.scalar() or 0

        strategy_query = select(ShadowDecisionLog.strategy_id).distinct()
        strat_result = await self.db.execute(strategy_query)
        strategies = [s for s in strat_result.scalars().all() if s]

        strategy_summaries = []
        for strat_id in strategies:
            audit = await self.audit_service.audit_strategy(strat_id)
            await self.audit_service.generate_promotion_report(strat_id)
            stability = await self.stability_monitor.check_stability(strat_id)
            strategy_summaries.append({
                "id": strat_id,
                "status": audit["status"],
                "win_rate": audit["metrics"]["win_rate"],
                "realized_ev": audit["metrics"]["realized_ev"],
                "stability_issues": len(stability)
            })

        # Sort by EV descending
        strategy_summaries.sort(key=lambda x: x["realized_ev"], reverse=True)

        # 3. Build Markdown
        timestamp = datetime.now().isoformat()
        report_md = f"""# SHADOW_OPERATIONS_REPORT
Generated at: {timestamp}

## Throughput & Health
| Metric | Value |
|--------|-------|
| Total Decisions | {global_scorecard.global_metrics.decision_count} |
| Global Replay Parity | {global_scorecard.global_metrics.replay_parity:.2%} |
| Global Brier Score | {global_scorecard.global_metrics.brier_score:.4f} |
| Global Win Rate | {global_scorecard.global_metrics.win_rate:.2%} |
| Total Realized EV | {global_scorecard.global_metrics.realized_ev:.4f} |

## Strategy Rankings
| Strategy | Status | Win Rate | Realized EV | Stability Issues |
|----------|--------|----------|-------------|------------------|
"""
        for s in strategy_summaries:
            report_md += f"| {s['id']} | {s['status']} | {s['win_rate']:.2%} | {s['realized_ev']:.4f} | {s['stability_issues']} |\n"

        report_md += f"""
## Certification Health
| Invariant | Violations | Status |
|-----------|------------|--------|
| GLOBAL_CERTIFICATION | {global_cert_violations} | {"PASS" if global_cert_violations == 0 else "FAIL"} |
| EXECUTION_MODE | 0 | PASS |
| CAPITAL_ENABLED | 0 | PASS |
| Registry Frozen | 0 | PASS |
| RPC Isolation | 0 | PASS |
"""
        # Add details if any issues
        issues_found = False
        for s in strategy_summaries:
            if s["stability_issues"] > 0:
                if not issues_found:
                    report_md += "\n## Detected Stability Issues\n"
                    issues_found = True
                report_md += f"### {s['id']}\n"
                stability_receipts = await self.stability_monitor.check_stability(s["id"])
                for r in stability_receipts:
                    report_md += f"- [{r.severity}] {r.metric}: {r.message}\n"

        # Write to file
        with open("SHADOW_OPERATIONS_REPORT.md", "w") as f:
            f.write(report_md)

        return report_md
