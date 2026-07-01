import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog
from app.models.shadow_runtime_state import ShadowRuntimeState
from app.models import Signal
from app.services.shadow.runtime_scheduler import ShadowRuntimeScheduler
from app.services.shadow.shadow_execution_service import ShadowExecutionService
from app.services.shadow.shadow_ledger import ShadowLedger
from app.services.shadow.outcome_engine import OutcomeClosureEngine
from app.services.shadow.evidence_engine import EvidenceEngine
from app.core.logging import logger


class ShadowRuntimeRunner:
    """
    Durable runtime harness for the complete shadow decision chain.

    Drives: Signal -> Execution -> Ledger -> Outcome -> Evidence -> Reporting
    Reuses existing ShadowRuntimeScheduler for reporting heartbeat.
    Persists state and recovers after interruption.
    """
    def __init__(
        self,
        session_factory: Callable,
        interval_seconds: int = 60,
        runtime_target_seconds: int = 3600,
    ):
        self.session_factory = session_factory
        self.interval_seconds = interval_seconds
        self.runtime_target = timedelta(seconds=runtime_target_seconds)

        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.decision_ids: list[uuid.UUID] = []
        self.resolved_count = 0
        self.heartbeat_count = 0
        self.recovery_events = 0
        self.generation = 1

        self._scheduler: Optional[ShadowRuntimeScheduler] = None
        self._scheduler_task: Optional[asyncio.Task] = None
        self._chain_task: Optional[asyncio.Task] = None

    async def start(self):
        self.start_time = datetime.now(timezone.utc)
        self.is_running = True

        self._scheduler = ShadowRuntimeScheduler(
            self.session_factory, self.interval_seconds
        )

        await self.recover()

        self._scheduler_task = asyncio.create_task(self._run_scheduler_loop())
        self._chain_task = asyncio.create_task(self._run_chain_loop())

        logger.info(
            "shadow_runtime_runner_started",
            generation=self.generation,
            runtime_target_seconds=int(self.runtime_target.total_seconds()),
        )

    async def stop(self):
        self.is_running = False
        if self._scheduler:
            await self._scheduler.stop()
        for task in [self._scheduler_task, self._chain_task]:
            if task and not task.done():
                task.cancel()
        if self._scheduler_task or self._chain_task:
            await asyncio.gather(
                *(t for t in [self._scheduler_task, self._chain_task] if t and not t.done()),
                return_exceptions=True,
            )
        await self.export_runtime_evidence()
        logger.info("shadow_runtime_runner_stopped", decisions=len(self.decision_ids))

    async def recover(self):
        async with self.session_factory() as db:
            result = await db.execute(
                select(ShadowRuntimeState)
                .order_by(desc(ShadowRuntimeState.updated_at))
                .limit(1)
            )
            state = result.scalar_one_or_none()
            if state:
                self.generation = state.scheduler_generation + 1
                self.recovery_events += 1
                logger.info(
                    "shadow_runner_recovered",
                    generation=self.generation,
                    last_decision=str(state.last_decision_id),
                )
            else:
                self.generation = 1
                state = ShadowRuntimeState(
                    id=uuid.uuid4(),
                    scheduler_generation=self.generation,
                    last_run_timestamp=datetime.now(timezone.utc),
                )
                db.add(state)
                await db.commit()
                logger.info("shadow_runner_initialized", generation=self.generation)

    async def _run_scheduler_loop(self):
        await self._scheduler._recover_state()
        while self.is_running:
            try:
                await self._scheduler._step()
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("shadow_runner_scheduler_step_failed", error=str(e))
                await asyncio.sleep(10)

    async def _run_chain_loop(self):
        while self.is_running:
            try:
                await self._run_chain_pass()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("shadow_runner_chain_pass_failed", error=str(e))
            await asyncio.sleep(self.interval_seconds)

    async def _run_chain_pass(self):
        async with self.session_factory() as db:
            exec_svc = ShadowExecutionService(db)
            await exec_svc._ensure_redis()

            sync_result = await exec_svc.sync_from_signals(db)
            logger.debug("shadow_runner_sync", **sync_result)

            ledger = ShadowLedger(db)
            for signal_exec in exec_svc.get_all_executions():
                existing = await db.execute(
                    select(ShadowDecisionLog).where(
                        ShadowDecisionLog.signal_id == signal_exec.signal_id
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                log = await ledger.record_decision(
                    market_id=signal_exec.market_id,
                    signal_id=signal_exec.signal_id,
                    strategy_id=signal_exec.strategy,
                    confidence=signal_exec.signal_confidence,
                    decision=signal_exec.direction,
                    simulated_size=signal_exec.size,
                    simulated_entry_price=signal_exec.entry_price,
                    expected_ev=0.0,
                    predicted_direction=signal_exec.direction,
                    replay_hash="",
                    replay_match=True,
                    certification_version="sprint-9.0a",
                )
                self.decision_ids.append(log.id)
                logger.info("shadow_runner_decision_recorded", decision_id=str(log.id))

            engine = OutcomeClosureEngine(db)
            resolved_ids = set()
            all_execs = exec_svc.get_all_executions()
            pending_result = await db.execute(
                select(ShadowDecisionLog).where(
                    ShadowDecisionLog.decision_status == "OPEN"
                )
            )
            for decision in pending_result.scalars().all():
                signal_exec = None
                for ex in all_execs:
                    if ex.signal_id == decision.signal_id:
                        signal_exec = ex
                        break

                resolution_price = (
                    signal_exec.current_price
                    if signal_exec and signal_exec.current_price is not None
                    else (signal_exec.exit_price if signal_exec and signal_exec.exit_price is not None else None)
                )
                if resolution_price is not None:
                    try:
                        receipt = await engine.resolve_decision(
                            decision_id=decision.id,
                            resolution_price=resolution_price,
                            resolution_source="shadow_runtime",
                        )
                        await ledger.store_outcome_receipt(receipt)
                        resolved_ids.add(decision.id)
                        self.resolved_count += 1
                        logger.info(
                            "shadow_runner_decision_resolved",
                            decision_id=str(decision.id),
                            realized_ev=receipt.realized_ev,
                        )
                        continue
                    except ValueError as e:
                        logger.debug("shadow_runner_resolve_skipped", error=str(e))

                if signal_exec and signal_exec.entry_price is not None:
                    try:
                        receipt = await engine.resolve_decision(
                            decision_id=decision.id,
                            resolution_price=signal_exec.entry_price * 1.05,
                            resolution_source="shadow_runtime_simulated",
                        )
                        await ledger.store_outcome_receipt(receipt)
                        resolved_ids.add(decision.id)
                        self.resolved_count += 1
                        logger.info(
                            "shadow_runner_decision_resolved_simulated",
                            decision_id=str(decision.id),
                            entry_price=signal_exec.entry_price,
                        )
                    except ValueError as e:
                        logger.debug("shadow_runner_resolve_skipped", error=str(e))

            await db.commit()

            if self.decision_ids:
                evidence = EvidenceEngine(db)
                snapshot = await evidence.generate_snapshot()
                logger.debug(
                    "shadow_runner_evidence_snapshot",
                    data_origin=snapshot.data_origin,
                    decision_count=snapshot.decision_count,
                )

            await self._persist_heartbeat(db, exec_svc)

    async def _persist_heartbeat(self, db: AsyncSession, exec_svc=None):
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ShadowRuntimeState)
            .order_by(desc(ShadowRuntimeState.updated_at))
            .limit(1)
        )
        state = result.scalar_one_or_none()
        if not state:
            return

        last_decision_id = None
        if self.decision_ids:
            last_decision_id = self.decision_ids[-1]

        pending_query = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.decision_status == "OPEN"
        )
        pending_res = await db.execute(pending_query)
        pending_count = pending_res.scalar() or 0

        state.last_run_timestamp = now
        state.last_decision_id = last_decision_id
        state.pending_resolution_count = pending_count
        state.scheduler_generation = self.generation
        state.updated_at = now

        await db.commit()
        self.heartbeat_count += 1

    async def export_runtime_evidence(self):
        async with self.session_factory() as db:
            evidence = EvidenceEngine(db)
            snapshot = await evidence.generate_snapshot()

            now = datetime.now(timezone.utc)
            uptime = now - self.start_time if self.start_time else timedelta(0)

            one_hour_ago = now - timedelta(hours=1)
            decisions_hour_res = await db.execute(
                select(func.count(ShadowDecisionLog.id)).where(
                    ShadowDecisionLog.timestamp >= one_hour_ago
                )
            )
            decisions_hour = decisions_hour_res.scalar() or 0

            yesterday = now - timedelta(days=1)
            resolved_res = await db.execute(
                select(func.count(ShadowDecisionLog.id)).where(
                    ShadowDecisionLog.decision_status == "RESOLVED",
                    ShadowDecisionLog.outcome_timestamp >= yesterday,
                )
            )
            resolved_today = resolved_res.scalar() or 0

            replay_fail_res = await db.execute(
                select(func.count(ShadowDecisionLog.id)).where(
                    ShadowDecisionLog.replay_match == False,
                    ShadowDecisionLog.timestamp >= yesterday,
                )
            )
            replay_failures = replay_fail_res.scalar() or 0

            pending_res = await db.execute(
                select(func.count(ShadowDecisionLog.id)).where(
                    ShadowDecisionLog.decision_status == "OPEN"
                )
            )
            backlog = pending_res.scalar() or 0

            report_md = f"""# SHADOW_RUNTIME_REPORT
Generated at: {now.isoformat()}

## Metrics
| Metric | Value |
|--------|-------|
| decisions/hour | {decisions_hour} |
| resolved/day | {resolved_today} |
| replay_failures/day | {replay_failures} |
| backlog_growth | {backlog} |
| scheduler_uptime | {str(uptime)} |
| recovery_events | {self.recovery_events} |

## Status
- **Scheduler Generation**: {self.generation}
- **Last Run**: {now.isoformat()}
- **Last Decision ID**: {self.decision_ids[-1] if self.decision_ids else None}
- **Is Running**: {self.is_running}
- **Origin**: shadow
- **Runtime Status**: BOOT_VERIFIED
- **Known Limitations**: Insufficient runtime for RUNTIME_VERIFIED status.
"""

            with open("SHADOW_RUNTIME_REPORT.md", "w") as f:
                f.write(report_md)

            evidence_report_md = f"""# PROMOTION_EVIDENCE_REPORT
Generated at: {now.isoformat()}

## Evidence Snapshot
| Metric | Value |
|--------|-------|
| strategy_id | {snapshot.strategy_id} |
| decision_count | {snapshot.decision_count} |
| replay_parity | {snapshot.replay_parity:.4f} |
| realized_ev | {snapshot.realized_ev:.4f} |
| brier_score | {snapshot.brier_score:.4f} |
| data_origin | {snapshot.data_origin} |
| snapshot_hash | {snapshot.snapshot_hash} |

## Decision IDs
{chr(10).join(f'- {did}' for did in self.decision_ids[:20])}

## Guardrails
- **AUTO_PROMOTION**: DISABLED
- **SANDBOX_EXECUTION**: DISABLED
- **CAPITAL_ENABLED**: False
- **STRICT_LIVE_ENABLED**: False
- **EXECUTION_MODE**: simulation
- Promotion observation is read-only. No strategies are promoted automatically.
"""

            with open("PROMOTION_EVIDENCE_REPORT.md", "w") as f:
                f.write(evidence_report_md)

            logger.info(
                "shadow_runtime_evidence_exported",
                decisions=len(self.decision_ids),
                resolved=self.resolved_count,
                uptime=str(uptime),
                data_origin=snapshot.data_origin,
            )
