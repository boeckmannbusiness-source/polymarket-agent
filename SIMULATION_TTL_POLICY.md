# Simulation TTL Policy

## Objective
Prevent stale simulation results from being used in execution candidates.

## TTL Parameters
- **Default TTL**: 150 slots (~1 minute on Solana).
- **Slot Drift Threshold**: 10 slots (default).

## Invalidation Rules
1. **TTL Expiration**: If `current_slot > expires_at_slot`, the simulation is marked `TTL_EXPIRED`.
2. **Slot Drift**: If `abs(current_slot - simulated_slot) > threshold`, the simulation is marked `SLOT_DRIFT`.

## Replay Behavior
Expired simulations remain **replayable** for historical audit and analysis but are **non-executable** for any real or sandbox deployment.

## Verification
`test_simulation_ttl_and_drift` confirms deterministic invalidation of stale simulations.
