# Simulation Replay Proof

## Objective
Ensure simulations are preserved and reproducible during replay without re-calling RPC.

## Mechanism
- `SimulationSnapshot` is embedded in `ExecutionTrace`.
- `ReplayEngine` retrieves simulation state from metadata.
- Replay logic is 100% offline (RPC calls are forbidden during replay).

## Evidence
`test_sandbox_run.py` confirms that `ExecutionResult` metadata correctly preserves simulation results after a replay.
