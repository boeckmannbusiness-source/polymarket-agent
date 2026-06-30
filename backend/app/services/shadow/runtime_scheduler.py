import asyncio
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_runtime_state import ShadowRuntimeState
from app.models.shadow_decision_log import ShadowDecisionLog
from app.core.logging import logger

class ShadowRuntimeScheduler:
    """
    Durable long-running shadow scheduler.
    Triggers intelligence evaluation and manages shadow decision lifecycle.
    """
    def __init__(self, session_factory: Callable, interval_seconds: int = 60):
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.generation = 0
        self.start_time = datetime.now(timezone.utc)
        self.recovery_events = 0
        self.decisions_this_hour = 0
        self._last_hour_check = self.start_time

    async def start(self):
        """Starts the continuous scheduler loop."""
        self.is_running = True
        await self._recover_state()
        logger.info("shadow_scheduler_started", interval=self.interval_seconds, generation=self.generation)

        while self.is_running:
            try:
                await self._step()
                await asyncio.sleep(self.interval_seconds)
            except Exception as e:
                logger.error("shadow_scheduler_step_failed", error=str(e), exc_info=True)
                await asyncio.sleep(10) # Backoff

    async def stop(self):
        """Gracefully stops the scheduler."""
        self.is_running = False
        logger.info("shadow_scheduler_stopping")

    async def _recover_state(self):
        """Implements idempotent recovery logic."""
        async with self.session_factory() as db:
            result = await db.execute(
                select(ShadowRuntimeState).order_by(desc(ShadowRuntimeState.updated_at)).limit(1)
            )
            state = result.scalar_one_or_none()

            if state:
                self.generation = state.scheduler_generation + 1
                self.recovery_events += 1
                logger.info("shadow_scheduler_recovered", generation=self.generation, last_decision=str(state.last_decision_id))
            else:
                self.generation = 1
                state = ShadowRuntimeState(
                    id=uuid.uuid4(),
                    scheduler_generation=self.generation,
                    last_run_timestamp=datetime.now(timezone.utc)
                )
                db.add(state)
                await db.commit()
                logger.info("shadow_scheduler_initialized", generation=self.generation)

    async def _step(self):
        """Single scheduler iteration."""
        now = datetime.now(timezone.utc)

        async with self.session_factory() as db:
            # Update runtime state
            latest_decision_query = select(ShadowDecisionLog).order_by(desc(ShadowDecisionLog.timestamp)).limit(1)
            latest_res = await db.execute(latest_decision_query)
            latest_decision = latest_res.scalar_one_or_none()

            pending_query = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.decision_status == "OPEN")
            pending_res = await db.execute(pending_query)
            pending_count = pending_res.scalar() or 0

            state_query = select(ShadowRuntimeState).order_by(desc(ShadowRuntimeState.updated_at)).limit(1)
            state_res = await db.execute(state_query)
            state = state_res.scalar_one()

            state.last_run_timestamp = now
            state.last_decision_id = latest_decision.id if latest_decision else None
            state.pending_resolution_count = pending_count
            state.scheduler_generation = self.generation

            await db.commit()

            # Generate Reports
            await self._report_metrics(db)

            from app.services.shadow.stability_engine import ShadowStabilityEngine
            stability_engine = ShadowStabilityEngine(db)

            # For each active strategy, generate stability report
            strat_q = select(ShadowDecisionLog.strategy_id).distinct()
            strat_res = await db.execute(strat_q)
            strategies = [s for s in strat_res.scalars().all() if s]
            for strat_id in strategies:
                await stability_engine.generate_stability_report(strat_id)

        # Update hour metrics
        if now - self._last_hour_check > timedelta(hours=1):
            self.decisions_this_hour = 0
            self._last_hour_check = now

    async def _report_metrics(self, db: AsyncSession):
        """Generates SHADOW_RUNTIME_REPORT.md."""
        now = datetime.now(timezone.utc)
        uptime = now - self.start_time

        # decisions/hour
        one_hour_ago = now - timedelta(hours=1)
        decisions_hour_query = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.timestamp >= one_hour_ago
        )
        decisions_hour_res = await db.execute(decisions_hour_query)
        self.decisions_this_hour = decisions_hour_res.scalar() or 0

        # Calculate resolved/day (last 24h)
        yesterday = now - timedelta(days=1)
        resolved_query = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.decision_status == "RESOLVED",
            ShadowDecisionLog.outcome_timestamp >= yesterday
        )
        resolved_res = await db.execute(resolved_query)
        resolved_today = resolved_res.scalar() or 0

        # Replay failures (last 24h)
        replay_fail_query = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.replay_match == False,
            ShadowDecisionLog.timestamp >= yesterday
        )
        replay_fail_res = await db.execute(replay_fail_query)
        replay_failures = replay_fail_res.scalar() or 0

        # Backlog growth
        state_query = select(ShadowRuntimeState).order_by(desc(ShadowRuntimeState.updated_at)).limit(1)
        state_res = await db.execute(state_query)
        state = state_res.scalar_one()
        backlog = state.pending_resolution_count

        report_md = f"""# SHADOW_RUNTIME_REPORT
Generated at: {now.isoformat()}

## Metrics
| Metric | Value |
|--------|-------|
| decisions/hour | {self.decisions_this_hour} |
| resolved/day | {resolved_today} |
| replay_failures/day | {replay_failures} |
| backlog_growth | {backlog} |
| scheduler_uptime | {str(uptime)} |
| recovery_events | {self.recovery_events} |

## Status
- **Scheduler Generation**: {self.generation}
- **Last Run**: {state.last_run_timestamp.isoformat()}
- **Last Decision ID**: {state.last_decision_id}
- **Is Running**: {self.is_running}
"""
        with open("SHADOW_RUNTIME_REPORT.md", "w") as f:
            f.write(report_md)
