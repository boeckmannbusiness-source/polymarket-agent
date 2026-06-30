import hashlib
from uuid import UUID
from typing import Dict, Any, Tuple
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shadow_decision_log import ShadowDecisionLog

class ShadowSamplingService:
    """
    Provides scalable observability by deterministically sampling decisions for audit and replay.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    def get_sampling_result(self, decision_id: UUID) -> Tuple[str, bool, str]:
        """
        Determines sampling bucket for a decision using deterministic hashing.
        Returns: (sample_reason, audit_candidate, sampling_bucket)
        """
        # Deterministic hash of UUID
        hasher = hashlib.md5(str(decision_id).encode())
        hash_int = int(hasher.hexdigest(), 16)
        bucket_val = hash_int % 100

        sampling_bucket = "PERSIST_ONLY"
        audit_candidate = False
        sample_reason = "Standard Persistence"

        # 100% Persistence (Implicit)

        # 5% Full Replay Verification
        if bucket_val < 5:
            sampling_bucket = "FULL_REPLAY"
            sample_reason = "Deterministic Replay Sample"

        # 1% Manual Audit Candidates (Subset of Full Replay or distinct)
        if bucket_val < 1:
            audit_candidate = True
            sampling_bucket = "MANUAL_AUDIT"
            sample_reason = "Manual Audit Candidate"

        return sample_reason, audit_candidate, sampling_bucket

    async def apply_sampling(self, decision_id: UUID):
        """Applies sampling to an existing decision log."""
        result = await self.db.execute(
            select(ShadowDecisionLog).where(ShadowDecisionLog.id == decision_id)
        )
        log_entry = result.scalar_one_or_none()
        if not log_entry:
            return

        reason, audit, bucket = self.get_sampling_result(decision_id)
        log_entry.sample_reason = reason
        log_entry.audit_candidate = audit
        log_entry.sampling_bucket = bucket

        await self.db.commit()

    async def generate_sampling_report(self):
        """Generates SHADOW_SAMPLING_REPORT.md."""
        # Total sampled (all decisions should have sampling metadata in this new world)
        total_q = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.sampling_bucket.isnot(None))
        total_res = await self.db.execute(total_q)
        sampled_count = total_res.scalar() or 0

        # Replay pass rate
        replay_total_q = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.sampling_bucket == "FULL_REPLAY")
        replay_total_res = await self.db.execute(replay_total_q)
        replay_total = replay_total_res.scalar() or 0

        replay_pass_q = select(func.count(ShadowDecisionLog.id)).where(
            ShadowDecisionLog.sampling_bucket == "FULL_REPLAY",
            ShadowDecisionLog.replay_match == True
        )
        replay_pass_res = await self.db.execute(replay_pass_q)
        replay_pass = replay_pass_res.scalar() or 0

        replay_pass_rate = (replay_pass / replay_total) if replay_total > 0 else 0.0

        # Audit queue size
        audit_q = select(func.count(ShadowDecisionLog.id)).where(ShadowDecisionLog.audit_candidate == True)
        audit_res = await self.db.execute(audit_q)
        audit_queue_size = audit_res.scalar() or 0

        now = datetime.now(timezone.utc)
        report_md = f"""# SHADOW_SAMPLING_REPORT
Generated at: {now.isoformat()}

## Metrics
| Metric | Value |
|--------|-------|
| sampled_count | {sampled_count} |
| replay_pass_rate | {replay_pass_rate:.2%} |
| audit_queue_size | {audit_queue_size} |

## Sampling Configuration
- **Full Replay**: 5%
- **Manual Audit**: 1%
- **Persistence**: 100%
- **Determinism**: MD5 Hashing
"""
        with open("SHADOW_SAMPLING_REPORT.md", "w") as f:
            f.write(report_md)
