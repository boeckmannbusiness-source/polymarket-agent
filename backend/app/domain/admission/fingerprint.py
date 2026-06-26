import hashlib
import json
from decimal import Decimal
from typing import List, Any
from app.domain.admission.models import AssetSnapshot, AdmissionDecision

class AdmissionFingerprint:
    @staticmethod
    def calculate(
        snapshot: AssetSnapshot,
        policy_version: str,
        decision: AdmissionDecision,
        reasons: List[str]
    ) -> str:
        """
        Calculates a deterministic SHA-256 fingerprint for admission decisions.
        """
        def serialize(obj: Any) -> Any:
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, AssetSnapshot):
                return obj.model_dump()
            if isinstance(obj, AdmissionDecision):
                return obj.value
            return obj

        payload = {
            "snapshot": snapshot.model_dump(),
            "policy_version": policy_version,
            "decision": decision.value,
            "reasons": sorted(reasons)
        }

        encoded = json.dumps(payload, sort_keys=True, default=serialize).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def verify(
        stored_hash: str,
        snapshot: AssetSnapshot,
        policy_version: str,
        decision: AdmissionDecision,
        reasons: List[str]
    ) -> bool:
        """
        Verifies if the recomputed hash matches the stored hash.
        """
        recomputed = AdmissionFingerprint.calculate(snapshot, policy_version, decision, reasons)
        return stored_hash == recomputed
