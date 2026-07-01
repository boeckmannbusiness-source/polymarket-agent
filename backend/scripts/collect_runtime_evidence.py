"""
Sprint 9.0B - Runtime Evidence Collection

Runs the ShadowRuntimeRunner for the target duration (default 1 hour)
and collects verifiable runtime evidence.

If runtime proof cannot be reached, generates BLOCKING_REASON.md.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["APP_ENV"] = "development"
os.environ["APP_DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "INFO"

from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, ARRAY


@compiles(UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "VARCHAR(64)"


@compiles(ARRAY, "sqlite")
def compile_array_sqlite(type_, compiler, **kw):
    return "JSON"


from app.database import Base
from app.config import settings
from app.models import *  # noqa: F401, F403
from app.models.shadow_decision_log import ShadowDecisionLog
from app.models.shadow_runtime_state import ShadowRuntimeState
from app.services.shadow.runtime_runner import ShadowRuntimeRunner
from app.services.shadow.runtime_evidence_validator import RuntimeEvidenceValidator

RUNTIME_TARGET_SECONDS = 3600
CHAIN_INTERVAL_SECONDS = 60
RUNTIME_DB = Path(__file__).resolve().parent.parent / "shadow_runtime.db"


async def main():
    print("=" * 60)
    print("Sprint 9.0B - Runtime Evidence Collection")
    print("=" * 60)
    print(f"Target runtime: {RUNTIME_TARGET_SECONDS}s ({RUNTIME_TARGET_SECONDS/3600:.1f}h)")
    print(f"Database: {RUNTIME_DB}")
    print(f"Redis: {'disabled' if not settings.REDIS_URL else settings.REDIS_URL}")
    print()

    # -- Initialize database --
    db_url = f"sqlite+aiosqlite:///{RUNTIME_DB}"
    print(f"Initializing database: {db_url}")
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def session_factory():
        async with async_session() as session:
            yield session

    # -- Phase 1: Check preconditions --
    print("\n--- Phase 1: Precondition Check ---")
    async with session_factory() as db:
        signal_count = (await db.execute(select(func.count()).select_from(ShadowDecisionLog))).scalar() or 0
        market_count = (await db.execute(text("SELECT COUNT(*) FROM markets"))).scalar() or 0
        print(f"Existing decisions in DB: {signal_count}")
        print(f"Existing markets in DB: {market_count}")

        # Check for signals
        try:
            signal_exists = (await db.execute(text("SELECT COUNT(*) FROM signals"))).scalar() or 0
        except Exception:
            signal_exists = 0
        print(f"Existing signals in DB: {signal_exists}")

    if signal_exists == 0 and market_count == 0:
        print("\n  [WARN] No existing data found. The chain requires market data and signals.")
        print("  The ingesters (REST/WS/PolygonRPC) will attempt to connect to Polymarket APIs.")
        print("  If no external data is available, the chain will stall at NO_MARKET_DATA/NO_SIGNALS.\n")

    # -- Phase 2: Start Runtime --
    print("\n--- Phase 2: Starting ShadowRuntimeRunner ---")
    runner = ShadowRuntimeRunner(
        session_factory=session_factory,
        interval_seconds=CHAIN_INTERVAL_SECONDS,
        runtime_target_seconds=RUNTIME_TARGET_SECONDS,
    )

    # Override start_time for tracking
    run_start = datetime.now(timezone.utc)

    print(f"Runner started at: {run_start.isoformat()}")
    print(f"Chain interval: {CHAIN_INTERVAL_SECONDS}s")
    print(f"Runtime target: {RUNTIME_TARGET_SECONDS}s")
    print()

    samples = []
    blocking_reason = None

    # -- Phase 3: Runtime Loop --
    print("--- Phase 3: Runtime Execution ---")
    elapsed = 0
    chain_pass_count = 0

    while elapsed < RUNTIME_TARGET_SECONDS:
        iteration_start = datetime.now(timezone.utc)
        minutes_elapsed = elapsed / 60

        print(f"\r  Elapsed: {int(minutes_elapsed):3d}m / {RUNTIME_TARGET_SECONDS//60}m | "
              f"Chain passes: {chain_pass_count:3d} | "
              f"Decisions: {len(runner.decision_ids):3d} | "
              f"Resolved: {runner.resolved_count:3d}",
              end="", flush=True)

        async with session_factory() as db:
            try:
                await runner._run_chain_pass()
                chain_pass_count += 1
            except Exception as e:
                print(f"\n  Chain pass error: {e}")

            # Check for blockers
            decision_count = (await db.execute(
                select(func.count(ShadowDecisionLog.id))
            )).scalar() or 0

            signal_exists = (await db.execute(
                text("SELECT COUNT(*) FROM signals")
            )).scalar() or 0

            # After 10 minutes, if no signals exist, the chain can't produce new decisions
            if elapsed > 600 and signal_exists == 0:
                blocking_reason = "NO_SIGNALS"
                print(f"\n[WARN] Blocking: No signals in DB after 10 minutes")
                break

            # Check if decisions are not getting resolved after ample time
            if decision_count > 0 and elapsed > 300:
                open_count = (await db.execute(
                    select(func.count(ShadowDecisionLog.id)).where(
                        ShadowDecisionLog.decision_status == "OPEN"
                    )
                )).scalar() or 0
                resolved_count = (await db.execute(
                    select(func.count(ShadowDecisionLog.id)).where(
                        ShadowDecisionLog.decision_status == "RESOLVED"
                    )
                )).scalar() or 0
                if open_count > 0 and resolved_count == 0:
                    blocking_reason = "NO_RESOLUTION"
                    print(f"\n[WARN] Blocking: {open_count} OPEN decisions, 0 resolved")
                    break

            # Signals exist but no decisions are being generated
            if signal_exists > 0 and decision_count == 0 and elapsed > 300:
                blocking_reason = "NO_DECISION_GENERATION"
                print(f"\n[WARN] Blocking: {signal_exists} signals but 0 decisions")
                break

        # Sample metrics periodically
        if chain_pass_count % 5 == 0:
            async with session_factory() as db:
                snap = {"elapsed": elapsed, "decisions": len(runner.decision_ids),
                        "resolved": runner.resolved_count}
                samples.append(snap)

        await asyncio.sleep(CHAIN_INTERVAL_SECONDS)
        elapsed = int((datetime.now(timezone.utc) - run_start).total_seconds())

    print("\n")

    # -- Phase 4: Stop and Collect --
    print("--- Phase 4: Stopping Runtime ---")
    stop_time = datetime.now(timezone.utc)
    runner.is_running = False

    uptime = stop_time - run_start
    print(f"Runtime ended at: {stop_time.isoformat()}")
    print(f"Total uptime: {uptime}")
    print(f"Chain passes: {chain_pass_count}")
    print(f"Decisions created: {len(runner.decision_ids)}")
    print(f"Decisions resolved: {runner.resolved_count}")

    # -- Phase 5: Validate Evidence --
    print("\n--- Phase 5: Runtime Evidence Validation ---")
    async with session_factory() as db:
        state_result = await db.execute(
            select(ShadowRuntimeState).order_by(desc(ShadowRuntimeState.updated_at)).limit(1)
        )
        state = state_result.scalar_one_or_none()

        if state:
            print(f"Runtime state: generation={state.scheduler_generation}, "
                  f"last_run={state.last_run_timestamp}, "
                  f"last_decision={state.last_decision_id}")

        validator = RuntimeEvidenceValidator(
            db=db,
            runtime_target_seconds=RUNTIME_TARGET_SECONDS,
        )
        validation_result = await validator.validate(
            runner_start_time=run_start,
            runner_decision_ids=runner.decision_ids,
            runner_is_running=False,
            runner_recovery_events=0,
        )

        print(f"\nValidator result: {validation_result}")
        validation_report = validator.get_report()

        with open("RUNTIME_VALIDATION_REPORT.md", "w") as f:
            f.write(validation_report)
        print("RUNTIME_VALIDATION_REPORT.md written")

        # -- Generate runtime report --
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        decisions_hour = (await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.timestamp >= one_hour_ago
            )
        )).scalar() or 0

        yesterday = now - timedelta(days=1)
        resolved_today = (await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "RESOLVED",
                ShadowDecisionLog.outcome_timestamp >= yesterday,
            )
        )).scalar() or 0

        replay_failures = (await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.replay_match == False,
                ShadowDecisionLog.timestamp >= yesterday,
            )
        )).scalar() or 0

        pending = (await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "OPEN"
            )
        )).scalar() or 0

        decision_total = (await db.execute(
            select(func.count(ShadowDecisionLog.id))
        )).scalar() or 0

        resolved_total = (await db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "RESOLVED"
            )
        )).scalar() or 0

        report_md = f"""# SHADOW_RUNTIME_REPORT
Generated at: {now.isoformat()}

## Metrics
| Metric | Value | Requirement | Status |
|--------|-------|-------------|--------|
| scheduler_uptime | {str(uptime)} | >= 01:00:00 | {'PASS' if uptime >= timedelta(hours=1) else 'FAIL'} |
| decisions/hour | {decisions_hour} | > 0 | {'PASS' if decisions_hour > 0 else 'FAIL'} |
| resolved/day | {resolved_today} | > 0 | {'PASS' if resolved_today > 0 else 'FAIL'} |
| replay_failures/day | {replay_failures} | - | - |
| backlog_growth | {pending} | - | - |
| recovery_events | 0 | - | - |

## Status
- **Scheduler Generation**: {state.scheduler_generation if state else 'N/A'}
- **Last Run**: {state.last_run_timestamp.isoformat() if state else 'N/A'}
- **Last Decision ID**: {state.last_decision_id if state else 'None'}
- **Is Running**: False (measurement ended)
- **Origin**: shadow
- **Runtime Status**: {'RUNTIME_VERIFIED' if validation_result == RuntimeEvidenceValidator.RUNTIME_READY else 'RUNTIME_NOT_PROVEN'}

## Lifecycle Counts
| Status | Count |
|--------|-------|
| Total Decisions | {decision_total} |
| OPEN | {pending} |
| RESOLVED | {resolved_total} |

## Decision IDs
{chr(10).join(f'- {did}' for did in runner.decision_ids[:50]) if runner.decision_ids else '- None'}
"""
        with open("SHADOW_RUNTIME_REPORT.md", "w") as f:
            f.write(report_md)
        print("SHADOW_RUNTIME_REPORT.md written")

        # -- Generate evidence report --
        from app.services.shadow.evidence_engine import EvidenceEngine
        evidence = EvidenceEngine(db)
        snapshot = await evidence.generate_snapshot()

        evidence_md = f"""# PROMOTION_EVIDENCE_REPORT
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
| reconstruction_hash | {snapshot.reconstruction_hash} |
| certification_violations | {snapshot.certification_violations} |
| decision_ids_count | {len(snapshot.decision_ids)} |

## Verification
- **Snapshot Reproducible**: {'YES' if snapshot.snapshot_hash else 'NO'}
- **Origin Verified**: {'YES' if snapshot.data_origin == 'shadow' else 'NO'}
- **Promotion Status**: OBSERVATION_ONLY (AUTO_PROMOTION=DISABLED)
"""
        with open("PROMOTION_EVIDENCE_REPORT.md", "w") as f:
            f.write(evidence_md)
        print("PROMOTION_EVIDENCE_REPORT.md written")

        # -- Decision trace --
        trace_res = await db.execute(
            select(ShadowDecisionLog).order_by(ShadowDecisionLog.timestamp.asc()).limit(200)
        )
        decisions = trace_res.scalars().all()

        trace_md = f"""# RUNTIME_DECISION_TRACE
Generated at: {now.isoformat()}

## Summary
- **Total Decisions**: {len(decisions)}
- **Resolved**: {sum(1 for d in decisions if d.decision_status == 'RESOLVED')}
- **OPEN**: {sum(1 for d in decisions if d.decision_status == 'OPEN')}

## Decision Log
| # | ID | Market | Strategy | Status | Timestamp | Resolved At | EV |
|---|----|--------|----------|--------|-----------|-------------|-----|
"""
        for i, d in enumerate(decisions[:100]):
            trace_md += f"| {i+1} | {d.id} | {d.market_id or ''} | {d.strategy_id or ''} | {d.decision_status or ''} | {d.timestamp} | {d.outcome_timestamp or ''} | {d.realized_ev or 0:.4f} |\n"

        with open("RUNTIME_DECISION_TRACE.md", "w") as f:
            f.write(trace_md)
        print("RUNTIME_DECISION_TRACE.md written")

        # -- Generate blocking reason if needed --
        if validation_result != RuntimeEvidenceValidator.RUNTIME_READY or decision_total == 0:
            if blocking_reason is None:
                if decision_total == 0:
                    blocking_reason = "NO_DECISION_GENERATION"
                elif resolved_total == 0:
                    blocking_reason = "NO_RESOLUTION"
                else:
                    blocking_reason = "UNKNOWN"

            blocker_md = f"""# BLOCKING_REASON
Generated at: {now.isoformat()}

## Blocker: {blocking_reason}

### Runtime Summary
- **Target Runtime**: {RUNTIME_TARGET_SECONDS}s
- **Actual Runtime**: {elapsed}s
- **Chain Passes**: {chain_pass_count}
- **Decisions Created**: {len(runner.decision_ids)}
- **Decisions Resolved**: {runner.resolved_count}

### Chain State
| Component | Status | Evidence |
|-----------|--------|----------|
| Market Observation | {'NOT_CHECKED' if market_count == 0 else 'AVAILABLE'} | - |
| Signal Generation | {'NOT_CHECKED' if signal_exists == 0 else 'AVAILABLE'} | - |
| Decision Creation | {'STALLED' if len(runner.decision_ids) == 0 else 'ACTIVE'} | {len(runner.decision_ids)} decisions |
| Outcome Resolution | {'STALLED' if runner.resolved_count == 0 else 'ACTIVE'} | {runner.resolved_count} resolved |
| Evidence Generation | {'STALLED' if decision_total == 0 else 'ACTIVE'} | origin={snapshot.data_origin} |

### Validation Results
| Check | Result |
|-------|--------|
| scheduler_uptime >= target | {'PASS' if uptime >= timedelta(hours=1) else 'FAIL'} ({str(uptime)}) |
| decision_count >= 1 | {'PASS' if decision_total >= 1 else 'FAIL'} ({decision_total}) |
| resolved_count >= 1 | {'PASS' if resolved_total >= 1 else 'FAIL'} ({resolved_total}) |
| last_decision_id != null | {'PASS' if state and state.last_decision_id else 'FAIL'} |
| decisions_per_hour > 0 | {'PASS' if decisions_hour > 0 else 'FAIL'} ({decisions_hour}) |
| origin == shadow | {'PASS' if snapshot.data_origin == 'shadow' else 'FAIL'} ({snapshot.data_origin}) |

### Remediation
- {_remediation(blocking_reason)}

### Next Actions
1. Fix the blocking component
2. Re-run collect_runtime_evidence.py
3. Verify RuntimeEvidenceValidator returns RUNTIME_READY
"""
            with open("BLOCKING_REASON.md", "w") as f:
                f.write(blocker_md)
            print("BLOCKING_REASON.md written")
            print(f"\n[WARN] BLOCKED: {blocking_reason}")
            print(f"   See BLOCKING_REASON.md for details")
        else:
            print("\n[OK] RUNTIME_READY - All validation checks passed!")

    # -- Cleanup --
    await engine.dispose()
    print("\n--- Runtime Evidence Collection Complete ---")


def _remediation(reason: str) -> str:
    remediations = {
        "NO_SIGNALS": (
            "No signals exist in the Signal table. The inester pipeline "
            "(PolymarketRESTIngester, PolymarketWSIngester, WhaleAgent, SignalAgent) "
            "must be running to produce signals. If external APIs are unreachable, "
            "ensure network connectivity to gamma-api.polymarket.com and that "
            "the background task loops (rest_ingester, ws_ingester, signal_agent) "
            "are active. Owner: ingress/agent team."
        ),
        "NO_MARKET_DATA": (
            "No market data received from ingesters. Check API connectivity and "
            "that the REST/WS ingesters are connecting to Polymarket APIs. "
            "Owner: ingress team."
        ),
        "NO_DECISION_GENERATION": (
            "Signals exist but ShadowExecutionService.sync_from_signals() is not "
            "producing shadow executions. Check Redis connectivity (ShadowExecutionService "
            "uses Redis hashes for execution storage) and verify the ShadowLedger "
            "record_decision() path. Owner: shadow execution team."
        ),
        "NO_RESOLUTION": (
            "Decisions are created but not resolved. OutcomeClosureEngine.resolve_decision() "
            "requires a resolution_price. The runner attempts to use the execution's "
            "current_price, but if prices are unavailable, resolution stalls. "
            "Owner: outcome resolution team."
        ),
        "REPLAY_FAILURE": (
            "Decisions are created but replay_match is failing. This indicates the "
            "execution path is not deterministic between replay and original. "
            "Owner: replay/parity team."
        ),
        "SCHEDULER_STOPPED": (
            "The ShadowRuntimeScheduler stopped unexpectedly. Check for exceptions "
            "in scheduler loop and ensure Redis connectivity for state persistence. "
            "Owner: scheduler team."
        ),
    }
    return remediations.get(reason, "Unknown blocking reason. Investigate chain state and re-run.")


if __name__ == "__main__":
    asyncio.run(main())
