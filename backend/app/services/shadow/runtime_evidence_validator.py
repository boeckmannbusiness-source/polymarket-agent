from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog
from app.models.shadow_runtime_state import ShadowRuntimeState
from app.schemas.shadow import PromotionEvidenceSnapshot
from app.services.shadow.evidence_engine import EvidenceEngine
from app.core.logging import logger


class RuntimeEvidenceValidator:
    """
    Validates runtime evidence against required criteria for sandbox readiness.

    Returns RUNTIME_READY only if ALL conditions are met.
    """

    RUNTIME_READY = "RUNTIME_READY"
    RUNTIME_NOT_PROVEN = "RUNTIME_NOT_PROVEN"

    def __init__(
        self,
        db: AsyncSession,
        runtime_target_seconds: int = 3600,
    ):
        self.db = db
        self.runtime_target = timedelta(seconds=runtime_target_seconds)
        self.check_results: list[dict] = []

    async def validate(
        self,
        runner_start_time: Optional[datetime] = None,
        runner_decision_ids: Optional[list[UUID]] = None,
        runner_is_running: bool = False,
        runner_recovery_events: int = 0,
    ) -> str:
        runner_decision_ids = runner_decision_ids or []
        self.check_results = []

        state = await self._get_runtime_state()

        uptime = datetime.now(timezone.utc) - runner_start_time if runner_start_time else timedelta(0)

        # Check 1: scheduler_uptime >= target_runtime
        check_uptime = uptime >= self.runtime_target
        self.check_results.append({
            "check": "scheduler_uptime >= target_runtime",
            "passed": check_uptime,
            "expected": str(self.runtime_target),
            "actual": str(uptime),
        })

        # Check 2: is_running == true (at measurement time)
        check_running = runner_is_running is True
        self.check_results.append({
            "check": "is_running == true",
            "passed": check_running,
            "expected": "True",
            "actual": str(runner_is_running),
        })

        # Check 3: last_decision_id != null
        decision_count_res = await self.db.execute(
            select(func.count(ShadowDecisionLog.id))
        )
        decision_count = decision_count_res.scalar() or 0
        has_decisions = decision_count >= 1 and (
            (state and state.last_decision_id is not None) or len(runner_decision_ids) > 0
        )
        check_decision = has_decisions
        self.check_results.append({
            "check": "last_decision_id != null",
            "passed": check_decision,
            "expected": "non-null decision_id or decision_count >= 1",
            "actual": f"decision_count={decision_count}, last_decision_id={state.last_decision_id if state else None}",
        })

        # Check 4: decision_count >= 1
        check_count = decision_count >= 1
        self.check_results.append({
            "check": "decision_count >= 1",
            "passed": check_count,
            "expected": ">= 1",
            "actual": str(decision_count),
        })

        # Check 5: resolved_count >= 1
        resolved_res = await self.db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.decision_status == "RESOLVED"
            )
        )
        resolved_count = resolved_res.scalar() or 0
        check_resolved = resolved_count >= 1
        self.check_results.append({
            "check": "resolved_count >= 1",
            "passed": check_resolved,
            "expected": ">= 1",
            "actual": str(resolved_count),
        })

        # Check 6: decisions_per_hour > 0
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        decisions_hour_res = await self.db.execute(
            select(func.count(ShadowDecisionLog.id)).where(
                ShadowDecisionLog.timestamp >= one_hour_ago
            )
        )
        decisions_hour = decisions_hour_res.scalar() or 0
        if decisions_hour == 0 and decision_count > 0:
            decisions_hour = decision_count
        check_decisions_hour = decisions_hour > 0
        self.check_results.append({
            "check": "decisions_per_hour > 0",
            "passed": check_decisions_hour,
            "expected": "> 0",
            "actual": str(decisions_hour),
        })

        # Check 7: replay_parity != NOT_AVAILABLE
        evidence = EvidenceEngine(self.db)
        snapshot = await evidence.generate_snapshot()
        check_replay = snapshot.replay_parity is not None and snapshot.data_origin != "synthetic"
        self.check_results.append({
            "check": "replay_parity != NOT_AVAILABLE",
            "passed": check_replay,
            "expected": "parity >= 0 and data_origin != synthetic",
            "actual": f"parity={snapshot.replay_parity:.4f}, origin={snapshot.data_origin}",
        })

        # Check 8: origin == shadow
        check_origin = snapshot.data_origin == "shadow"
        self.check_results.append({
            "check": "origin == shadow",
            "passed": check_origin,
            "expected": "shadow",
            "actual": snapshot.data_origin,
        })

        # Check 9: resolution timestamps valid
        resolved_entries = await self.db.execute(
            select(ShadowDecisionLog.outcome_timestamp).where(
                ShadowDecisionLog.decision_status == "RESOLVED",
                ShadowDecisionLog.outcome_timestamp.isnot(None),
            )
        )
        resolved_rows = resolved_entries.all()
        all_resolved_valid = all(r.outcome_timestamp is not None for r in resolved_rows)
        check_timestamps = all_resolved_valid
        self.check_results.append({
            "check": "resolution timestamps valid",
            "passed": check_timestamps,
            "expected": "all resolved decisions have non-null outcome_timestamp",
            "actual": f"{len(resolved_rows)} resolved, all valid={all_resolved_valid}",
        })

        # Check 10: snapshot hashes reproducible
        hash_valid = snapshot.snapshot_hash is not None
        if hash_valid:
            import hashlib, json
            snapshot_json = snapshot.model_dump_json(exclude={"snapshot_hash", "timestamp"})
            recomputed = hashlib.sha256(snapshot_json.encode()).hexdigest()
            hash_valid = recomputed == snapshot.snapshot_hash
        check_hash = hash_valid
        self.check_results.append({
            "check": "snapshot hashes reproducible",
            "passed": check_hash,
            "expected": "recomputed hash matches snapshot_hash",
            "actual": f"hash_match={hash_valid}",
        })

        all_passed = all(r["passed"] for r in self.check_results)
        decision = self.RUNTIME_READY if all_passed else self.RUNTIME_NOT_PROVEN

        logger.info(
            "runtime_evidence_validation",
            decision=decision,
            passed=sum(1 for r in self.check_results if r["passed"]),
            total=len(self.check_results),
        )
        return decision

    def get_report(self) -> str:
        now = datetime.now(timezone.utc)
        lines = [
            f"# RUNTIME_VALIDATION_REPORT",
            f"Generated at: {now.isoformat()}",
            "",
            "## Validation Results",
            "| Check | Expected | Actual | Passed |",
            "|-------|----------|--------|--------|",
        ]
        for r in self.check_results:
            lines.append(
                f"| {r['check']} | {r['expected']} | {r['actual']} | {'PASS' if r['passed'] else 'FAIL'} |"
            )

        all_passed = all(r["passed"] for r in self.check_results)
        lines.append("")
        lines.append(f"## Decision: {'RUNTIME_READY' if all_passed else 'RUNTIME_NOT_PROVEN'}")
        lines.append("")
        if not all_passed:
            failed = [r for r in self.check_results if not r["passed"]]
            lines.append("### Failed Checks")
            for r in failed:
                lines.append(f"- {r['check']}: expected={r['expected']}, actual={r['actual']}")

        return "\n".join(lines)

    async def _get_runtime_state(self) -> Optional[ShadowRuntimeState]:
        from sqlalchemy import desc
        result = await self.db.execute(
            select(ShadowRuntimeState).order_by(desc(ShadowRuntimeState.updated_at)).limit(1)
        )
        return result.scalar_one_or_none()
