# Admission Replay Proof

The system guarantees deterministic admission replay through SHA-256 fingerprinting.

## Fingerprint Components

The `AdmissionFingerprint` is calculated from:
1. `AssetSnapshot` (Immutable)
2. `PolicyVersion`
3. `AdmissionDecision`
4. `Reasons`

## Verification Mechanism

During replay:
1. Load `AssetSnapshot` from trace.
2. Load `AdmissionReceipt` from trace.
3. Recompute hash using `AdmissionFingerprint.calculate`.
4. Compare `stored_hash == recomputed_hash`.

If any bit of the snapshot or policy changes, the replay will fail with a `ValueError`, ensuring the integrity of the historical decision.
