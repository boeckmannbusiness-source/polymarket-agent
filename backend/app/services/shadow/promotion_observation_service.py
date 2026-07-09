from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.shadow.stability_engine import ShadowStabilityEngine

class PromotionObservationService:
    """
    Introduces observation-only readiness tracking for shadow strategies.
    Strictly read-only; no automatic promotion or execution capability.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.stability_engine = ShadowStabilityEngine(db)

    async def evaluate_readiness(self, strategy_id: str) -> Dict[str, Any]:
        """
        Determines the observation state of a strategy.
        Lifecycle: COLLECTING -> OBSERVING -> READY_CANDIDATE -> MANUAL_APPROVAL_REQUIRED
        """
        # Global metrics for this strategy
        query = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.strategy_id == strategy_id,
            ShadowDecisionLog.decision_status == "RESOLVED"
        )
        res = await self.db.execute(query)
        resolved_count = res.scalar() or 0

        # Stability metrics (30d)
        stability_30d = await self.stability_engine.compute_window_metrics(strategy_id, 30)

        state = "COLLECTING"
        reasons = []

        # Calculate avg_days_to_candidate (simulated projection)
        # Assuming we need 500 decisions and throughput is decisions/day
        throughput = stability_30d.get("throughput_trend", 0)
        if throughput > 0:
            avg_days_to_candidate = (500 - resolved_count) / throughput
            avg_days_to_candidate = max(0, avg_days_to_candidate)
        else:
            avg_days_to_candidate = None

        if resolved_count < 100:
            state = "COLLECTING"
            reasons.append(f"Insufficient volume: {resolved_count}/100 resolved decisions")
        elif resolved_count < 500:
            state = "OBSERVING"
            reasons.append(f"Observing stability: {resolved_count}/500 resolved decisions")
        else:
            # Check stability for candidate status
            if stability_30d.get("status") == "OK":
                ev_avg = stability_30d.get("realized_ev_avg", 0.0)
                replay_stab = stability_30d.get("replay_stability", 0.0)

                if ev_avg > 0 and replay_stab >= 0.95:
                    # Transition to READY_CANDIDATE
                    state = "READY_CANDIDATE"
                    reasons.append("Positive EV and high replay stability maintained over 30d")

                    # Logic for MANUAL_APPROVAL_REQUIRED:
                    # In a real system, this would check if it has been a candidate for X days.
                    # For Sprint 9.0, we'll transition if candidate and has > 90d window OK.
                    stability_90d = await self.stability_engine.compute_window_metrics(strategy_id, 90)
                    if stability_90d.get("status") == "OK" and resolved_count > 1000:
                         state = "MANUAL_APPROVAL_REQUIRED"
                         reasons.append("High volume stability reached. Manual approval required.")
                else:
                    state = "OBSERVING"
                    if ev_avg <= 0:
                        reasons.append("Negative or zero EV in 30d window")
                    if replay_stab < 0.95:
                        reasons.append(f"Replay stability {replay_stab:.2%} below 95% threshold")
            else:
                state = "OBSERVING"
                reasons.append("Awaiting 30d stability window data")

        return {
            "strategy_id": strategy_id,
            "state": state,
            "resolved_count": resolved_count,
            "reasons": reasons,
            "stability_30d": stability_30d,
            "avg_days_to_candidate": avg_days_to_candidate
        }

    async def generate_observation_report(self):
        """Generates PROMOTION_OBSERVATION_REPORT.md."""
        # Get all strategies
        strat_q = select(ShadowDecisionLog.strategy_id).distinct()
        strat_res = await self.db.execute(strat_q)
        strategies = [s for s in strat_res.scalars().all() if s]

        results = []
        for s in strategies:
            results.append(await self.evaluate_readiness(s))

        now = datetime.now(timezone.utc)
        report_md = f"# PROMOTION_OBSERVATION_REPORT\n"
        report_md += f"Generated at: {now.isoformat()}\n\n"

        # State distribution
        dist = {"COLLECTING": 0, "OBSERVING": 0, "READY_CANDIDATE": 0, "MANUAL_APPROVAL_REQUIRED": 0}
        for r in results:
            dist[r["state"]] = dist.get(r["state"], 0) + 1

        report_md += "## Readiness Distribution\n"
        for state, count in dist.items():
            report_md += f"- **{state}**: {count}\n"
        report_md += "\n"

        report_md += "## Strategy Status\n"
        report_md += "| Strategy | State | Resolved | 30d EV | Replay Stab | Days to Cand | Reasons |\n"
        report_md += "|----------|-------|----------|--------|-------------|--------------|---------|\n"

        for r in results:
            ev = r["stability_30d"].get("realized_ev_avg", "N/A")
            if isinstance(ev, float): ev = f"{ev:.4f}"

            stab = r["stability_30d"].get("replay_stability", "N/A")
            if isinstance(stab, float): stab = f"{stab:.2%}"

            dtc = r.get("avg_days_to_candidate")
            dtc_str = f"{dtc:.1f}" if dtc is not None else "N/A"

            reasons = "; ".join(r["reasons"])
            report_md += f"| {r['strategy_id']} | {r['state']} | {r['resolved_count']} | {ev} | {stab} | {dtc_str} | {reasons} |\n"

        report_md += "\n## Guardrails\n"
        report_md += "- **AUTO_PROMOTION**: DISABLED\n"
        report_md += "- **SANDBOX_EXECUTION**: DISABLED\n"
        report_md += "- READY_CANDIDATE status is informational only.\n"

        with open("PROMOTION_OBSERVATION_REPORT.md", "w") as f:
            f.write(report_md)

        return results
