# Simulation Hardening Report

## Objective
Harden the Solana read-only simulation layer for improved determinism and safety.

## Implementation
- **Simulation Fingerprinting**: `SimulationReceipt` now includes a SHA-256 hash of all critical simulation outputs (`tx_message`, `blockhash`, `slot`, `compute_units`, `estimated_fee`).
- **Hash Validation**: `ReplayEngine` recomputes and validates the hash during replay. Mismatches trigger `SimulationInvalidationError`.
- **Capability Snapshot**: `CapabilitySnapshot` is now bound to the `ExecutionTrace`, ensuring capability state (mode, permissions) is preserved and reconstructed.
- **Offline Enforcement**: `ReplayOfflineGuard` prevents any RPC calls during replay, ensuring 100% offline reproducibility.

## Verification
- `test_simulation_hardening_integrity` confirms hash mismatch rejection.
- `test_replay_offline_isolation_mocked` confirms RPC calls are blocked during replay.
