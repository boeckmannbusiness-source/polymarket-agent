from typing import Dict, Any, List
import hashlib
import json
from app.schemas.shadow import PromotionEvidenceSnapshot
from app.core.logging import logger

class ReportIntegrityError(Exception):
    """Raised when a shadow report fails integrity validation."""
    pass

class ReportIntegrityValidator:
    """
    Validator for ensuring semantic and mathematical correctness of shadow intelligence reports.
    """

    def validate_snapshot(self, snapshot: PromotionEvidenceSnapshot, status: str) -> bool:
        """
        Validates a promotion evidence snapshot against policy and consistency rules.
        """
        # 1. Status Consistency
        if status == "READY" and snapshot.data_origin != "shadow":
            raise ReportIntegrityError(
                f"Status READY is incompatible with origin '{snapshot.data_origin}'. Expected 'shadow'."
            )

        # 2. Origin Consistency
        allowed_origins = ["shadow", "synthetic", "mixed"]
        if snapshot.data_origin not in allowed_origins:
             raise ReportIntegrityError(f"Invalid data origin: {snapshot.data_origin}")

        # Relaxed for reporting empty shadow state
        # if not snapshot.decision_ids and snapshot.data_origin != "synthetic":
        #      raise ReportIntegrityError(f"Origin '{snapshot.data_origin}' requires at least one decision ID.")

        # 3. Population Consistency
        if snapshot.decision_count != len(snapshot.decision_ids):
             raise ReportIntegrityError(
                 f"Population mismatch: decision_count={snapshot.decision_count}, but decision_ids length={len(snapshot.decision_ids)}"
             )

        # 4. Reconstruction Consistency (Sprint 8.4B)
        recon_data = {
            "decision_ids": [str(uid) for uid in snapshot.decision_ids],
            "resolution_range": [ts.isoformat() if ts else None for ts in snapshot.resolution_range],
            "source_tables": snapshot.source_tables
        }
        expected_recon_hash = hashlib.sha256(json.dumps(recon_data, sort_keys=True).encode()).hexdigest()

        if snapshot.reconstruction_hash != expected_recon_hash:
            raise ReportIntegrityError(
                f"Reconstruction hash mismatch! Snapshot data does not match reconstruction_hash."
            )

        return True

    def validate_parity_report(self, total: int, buckets: Dict[str, int]) -> bool:
        """
        Validates that replay parity buckets are mathematically consistent.
        """
        if total < 0:
            raise ReportIntegrityError("Total decisions cannot be negative.")

        sum_buckets = sum(buckets.values())
        if total != sum_buckets:
             raise ReportIntegrityError(
                 f"Parity bucket mismatch: sum of buckets ({sum_buckets}) != total resolved ({total})"
             )

        return True
