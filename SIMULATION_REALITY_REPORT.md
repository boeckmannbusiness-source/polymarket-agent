# SIMULATION REALITY REPORT

## Overview
Simulation has been upgraded from synthetic assumptions to chain-aware execution modeling.

## Enhancements
- **Compute Unit Reality**: Capture real units from RPC simulation and validate against planner assumptions.
- **Fee Reality**: Integrated `FeeEstimator` using `Decimal` precision for base and priority fees.
- **Route Reality**: `RouteValidator` enforces structure and existence checks.
- **Slippage Modeling**: `SlippageAnalyzer` calculates effective slippage and categorizes risk (LOW to REJECT).

## Chain Reality Proof
The `SimulationReceipt` now includes:
- `simulation_id`
- `account_state_hash` (derived from simulation result accounts)
- `slot` & `blockhash` from live RPC context
- `compute_delta` (real - expected)
- `fee_snapshot` & `slippage_snapshot`

## Replay Integrity
All new fields are hashed into `simulation_hash`, ensuring 100% offline replay determinism without RPC calls.
