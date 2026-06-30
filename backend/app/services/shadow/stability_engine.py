from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import math

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog

class ShadowStabilityEngine:
    """
    Computes rolling evaluation windows for strategy stability analysis.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_window_metrics(self, strategy_id: str, days: int) -> Dict[str, Any]:
        """
        Computes stability metrics for a given window of RESOLVED decisions.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=days)

        query = select(ShadowDecisionLog).where(
            ShadowDecisionLog.strategy_id == strategy_id,
            ShadowDecisionLog.decision_status == "RESOLVED",
            ShadowDecisionLog.outcome_timestamp >= cutoff
        )
        result = await self.db.execute(query)
        decisions = list(result.scalars().all())

        if not decisions:
            return {"status": "NOT_AVAILABLE"}

        count = len(decisions)
        realized_ev_total = sum(d.realized_ev or 0.0 for d in decisions)
        ev_avg = realized_ev_total / count

        # EV stability (standard deviation of EV)
        ev_variance = sum((d.realized_ev - ev_avg)**2 for d in decisions if d.realized_ev is not None) / count
        ev_stability = math.sqrt(ev_variance)

        # Replay stability (mean replay_match)
        replay_matches = [1.0 if d.replay_match else 0.0 for d in decisions if d.replay_match is not None]
        replay_stability = sum(replay_matches) / len(replay_matches) if replay_matches else 0.0

        # Calibration drift (mean actual_ev - expected_ev)
        calibration_deltas = [
            (d.actual_ev or 0.0) - (d.expected_ev or 0.0)
            for d in decisions
            if d.actual_ev is not None and d.expected_ev is not None
        ]
        calibration_drift = sum(calibration_deltas) / len(calibration_deltas) if calibration_deltas else 0.0

        # Throughput trend (decisions per day in this window)
        throughput = count / days

        return {
            "status": "OK",
            "decision_count": count,
            "realized_ev_avg": ev_avg,
            "ev_stability": ev_stability,
            "replay_stability": replay_stability,
            "calibration_drift": calibration_drift,
            "throughput_trend": throughput
        }

    async def generate_stability_report(self, strategy_id: str):
        """Generates SHADOW_STABILITY_REPORT.md for a strategy."""
        windows = [7, 30, 90]
        results = {}
        for d in windows:
            results[f"{d}d"] = await self.compute_window_metrics(strategy_id, d)

        now = datetime.now(timezone.utc)
        report_md = f"# SHADOW_STABILITY_REPORT\n"
        report_md += f"Strategy: {strategy_id}\n"
        report_md += f"Generated at: {now.isoformat()}\n\n"

        report_md += "| Metric | 7d | 30d | 90d |\n"
        report_md += "|--------|----|-----|-----|\n"

        metrics = [
            ("decision_count", "Decisions"),
            ("realized_ev_avg", "Avg EV"),
            ("ev_stability", "EV Stability (StdDev)"),
            ("replay_stability", "Replay Stability"),
            ("calibration_drift", "Calibration Drift"),
            ("throughput_trend", "Throughput (dec/day)")
        ]

        for key, label in metrics:
            row = f"| {label} "
            for d in windows:
                val = results[f"{d}d"].get(key, "N/A")
                if isinstance(val, float):
                    row += f"| {val:.4f} "
                else:
                    row += f"| {val} "
            report_md += row + "|\n"

        with open("SHADOW_STABILITY_REPORT.md", "w") as f:
            f.write(report_md)

        return results
