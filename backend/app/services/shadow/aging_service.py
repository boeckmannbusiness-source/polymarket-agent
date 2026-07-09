import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from sqlalchemy import select, func, update, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog
from app.core.logging import logger

# Default timeouts
OPEN_TIMEOUT = timedelta(hours=24)
CLOSED_TIMEOUT = timedelta(hours=48)

class ShadowAgingService:
    """
    Manages the lifecycle of shadow decisions, identifying stale decisions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_aging(self):
        """
        Transitions decisions to STALE if they exceed timeouts.
        OPEN beyond 24h -> STALE
        CLOSED beyond 48h -> STALE
        """
        now = datetime.now(timezone.utc)

        # OPEN stale
        open_cutoff = now - OPEN_TIMEOUT
        open_stale_q = update(ShadowDecisionLog).where(
            ShadowDecisionLog.decision_status == "OPEN",
            ShadowDecisionLog.timestamp < open_cutoff
        ).values(decision_status="STALE")

        # CLOSED stale
        closed_cutoff = now - CLOSED_TIMEOUT
        closed_stale_q = update(ShadowDecisionLog).where(
            ShadowDecisionLog.decision_status == "CLOSED",
            ShadowDecisionLog.outcome_timestamp < closed_cutoff
        ).values(decision_status="STALE")

        res_open = await self.db.execute(open_stale_q)
        res_closed = await self.db.execute(closed_stale_q)

        await self.db.commit()

        stale_count = res_open.rowcount + res_closed.rowcount
        if stale_count > 0:
            logger.info("shadow_aging_detected", stale_count=stale_count)

        return stale_count

    async def generate_aging_report(self):
        """Generates SHADOW_AGING_REPORT.md."""
        now = datetime.now(timezone.utc)

        # stale_count
        stale_q = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.decision_status == "STALE")
        stale_res = await self.db.execute(stale_q)
        stale_count = stale_res.scalar() or 0

        # avg_resolution_time (OPEN -> RESOLVED)
        # Use cross-dialect compatible approach instead of julianday
        res_time_q = select(ShadowDecisionLog.timestamp, ShadowDecisionLog.outcome_timestamp).where(
            ShadowDecisionLog.decision_status == "RESOLVED"
        )

        avg_res_hrs = 0.0
        try:
            res_time_res = await self.db.execute(res_time_q)
            rows = res_time_res.all()
            if rows:
                total_seconds = sum((r.outcome_timestamp - r.timestamp).total_seconds() for r in rows)
                avg_res_hrs = (total_seconds / len(rows)) / 3600.0
        except Exception as e:
            logger.warning("avg_resolution_time_calc_failed", error=str(e))

        # timeout_rate (STALE / (STALE + RESOLVED))
        resolved_q = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.decision_status == "RESOLVED")
        resolved_res = await self.db.execute(resolved_q)
        resolved_count = resolved_res.scalar() or 0

        total = stale_count + resolved_count
        timeout_rate = (stale_count / total) if total > 0 else 0.0

        report_md = f"""# SHADOW_AGING_REPORT
Generated at: {now.isoformat()}

## Metrics
| Metric | Value |
|--------|-------|
| stale_count | {stale_count} |
| avg_resolution_time (hrs) | {avg_res_hrs:.2f} |
| timeout_rate | {timeout_rate:.2%} |

## Configuration
- **OPEN_TIMEOUT**: {str(OPEN_TIMEOUT)}
- **CLOSED_TIMEOUT**: {str(CLOSED_TIMEOUT)}

## Status
- STALE decisions are excluded from promotion metrics.
"""
        with open("SHADOW_AGING_REPORT.md", "w") as f:
            f.write(report_md)
