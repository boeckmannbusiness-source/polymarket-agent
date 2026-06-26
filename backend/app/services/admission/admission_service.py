import uuid
import hashlib
import json
from decimal import Decimal
from typing import Optional, List, Dict, Any
from app.domain.admission.models import (
    AssetSnapshot,
    AdmissionDecision,
    AdmissionReceipt,
    MarketQualityDecision
)
from app.domain.admission.fingerprint import AdmissionFingerprint
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.services.admission.market_quality_engine import MarketQualityEngine
from app.services.admission.policy import AssetAdmissionPolicy
from app.core.logging import logger

class AdmissionService:
    def __init__(self):
        self._quality_engine = MarketQualityEngine()
        self._policy = AssetAdmissionPolicy()

    async def admit_asset(
        self,
        snapshot: AssetSnapshot,
        capabilities: CapabilitySnapshot,
        is_replay: bool = False,
        stored_receipt: Optional[AdmissionReceipt] = None
    ) -> AdmissionReceipt:
        """
        Evaluates an asset for admission. Supports deterministic replay.
        """
        if is_replay:
            if not stored_receipt:
                raise ValueError("AdmissionReceipt required for replay")
            return await self._replay_admission(snapshot, stored_receipt)

        # 1. Evaluate market quality
        quality_decision, quality_reasons = self._quality_engine.evaluate(snapshot)

        # 2. Apply admission policy
        decision, policy_reasons = self._policy.evaluate(quality_decision, snapshot, capabilities)

        all_reasons = sorted(list(set(quality_reasons + policy_reasons)))

        # 3. Create receipt
        admission_id = str(uuid.uuid4())

        # Calculate hashes
        snapshot_hash = hashlib.sha256(
            json.dumps(snapshot.model_dump(), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        decision_hash = AdmissionFingerprint.calculate(
            snapshot,
            self._policy.POLICY_VERSION,
            decision,
            all_reasons
        )

        receipt = AdmissionReceipt(
            admission_id=admission_id,
            decision=decision,
            decision_hash=decision_hash,
            asset_snapshot_hash=snapshot_hash,
            policy_version=self._policy.POLICY_VERSION,
            reasons=all_reasons,
            created_slot=snapshot.evaluation_slot,
            valid_until_slot=snapshot.evaluation_slot + 150 # TTL
        )

        logger.info("asset_admission_completed",
                    asset_id=snapshot.asset_id.canonical_id,
                    decision=decision,
                    reasons=all_reasons)

        return receipt

    async def _replay_admission(
        self,
        snapshot: AssetSnapshot,
        stored_receipt: AdmissionReceipt
    ) -> AdmissionReceipt:
        """
        Replays admission decision offline using only the snapshot and stored receipt.
        """
        # Re-verify the decision hash
        is_valid = AdmissionFingerprint.verify(
            stored_receipt.decision_hash,
            snapshot,
            stored_receipt.policy_version,
            stored_receipt.decision,
            stored_receipt.reasons
        )

        if not is_valid:
            logger.error("admission_replay_determinism_failure",
                         admission_id=stored_receipt.admission_id)
            raise ValueError("Deterministic admission replay failed: hash mismatch")

        # In replay, we return the stored receipt as-is (it's already verified)
        return stored_receipt
