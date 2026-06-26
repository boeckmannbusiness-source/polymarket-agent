# Asset Admission System

The Asset Admission System ensures that only high-quality assets are eligible for planning and simulation. It operates before any capital deployment or execution logic.

## Architecture

- **MarketQualityEngine**: Evaluates deterministic signals (market cap, liquidity, etc.).
- **AssetAdmissionPolicy**: Maps quality decisions to admission states.
- **AdmissionService**: Orchestrates the process and manages receipts.
- **AdmissionFingerprint**: Ensures deterministic replay.

## Decision States

- **ALLOW_SIMULATION**: Asset is approved for shadow trading and simulation.
- **WATCH**: Asset is allowed for simulation but with increased monitoring.
- **BLOCK**: Asset is completely ineligible for planning.

## Replay Determinism

All admission decisions are snapshotted and hashed. Replay validates the recomputed hash against the stored hash to ensure 100% reproducibility without RPC calls.
