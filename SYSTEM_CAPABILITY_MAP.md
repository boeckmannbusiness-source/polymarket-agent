# SYSTEM_CAPABILITY_MAP.md

## Capability Status

| Capability | Status | Evidence |
|------------|--------|----------|
| **observe_chain** | SUPPORTED | `SolanaRpcReader` provides read-only methods (`get_balance`, `get_latest_blockhash`, `get_account_info`) using `httpx.AsyncClient`. |
| **simulate_transaction** | SUPPORTED | `SolanaRpcReader.simulate_transaction` and `SolanaSimulationAdapter` allow for pre-flight verification without broadcast. |
| **wallet_signing** | SUPPORTED | `EphemeralWalletProvider` and `SigningSandbox` support local signing of transaction payloads in SANDBOX mode. |
| **asset_admission** | SUPPORTED | `AdmissionService` evaluates assets via `MarketQualityEngine` and `AssetAdmissionPolicy`, producing deterministic `AdmissionReceipt`s. |
| **capital_governance** | SUPPORTED | `CapitalGovernor` enforces `CapitalPolicy` and `ExposureModel` checks, producing hashed `RiskReceipt`s. |
| **execution** | BLOCKED | All execution paths are gated by `ExecutionGovernor` and directed to simulated adapters (`JupiterExecutionAdapter`, `SolanaSimulationAdapter`). |
| **broadcast** | BLOCKED | `NullRpcWriter` and `SandboxRpcWriter` explicitly raise `ExecutionAuthorizationError` on any `send_transaction` attempt. |
| **capital_deployment** | BLOCKED | `CapitalGuard` forces all `CapitalDecision`s to `BLOCK` when `capital_enabled` is False (default). |
| **replay** | SUPPORTED | `ReplayEngine` and `ReplayOfflineGuard` enable 100% offline verification of `ExecutionTrace` with tamper detection. |

## Detailed Boundary Verification

### Simulation ≠ Execution
- **Enforcement**: `ExecutionGovernor` mode-based permissions.
- **Blocking Layer**: `ExecutionService` checks `settings.EXECUTION_MODE`. In `SIMULATION`, `SIGN` and `RPC_WRITE` are missing.
- **Result**: PASS

### Wallet ≠ Broadcast
- **Enforcement**: `SigningSandbox` isolation.
- **Blocking Layer**: `SigningSandbox` does not contain any reference to a broadcast-capable RPC client; methods like `broadcast()` and `submit()` explicitly raise `PermissionError`.
- **Result**: PASS

### Admission ≠ Planning
- **Enforcement**: `Planner.plan()` sequence.
- **Blocking Layer**: `Planner._check_admission()` is called *before* any quoting or route planning; failure here raises `ValueError` and halts the pipeline.
- **Result**: PASS

### Capital ≠ Allocation
- **Enforcement**: `CapitalGuard.enforce()`.
- **Blocking Layer**: Even if `CapitalGovernor` allows a trade, `CapitalGuard` (the final step) overrides the decision to `BLOCK` based on global `capital_enabled` state.
- **Result**: PASS

### Replay ≠ RPC
- **Enforcement**: `ReplayOfflineGuard` (ContextVar-based).
- **Blocking Layer**: `SolanaRpcReader._post` checks `ReplayOfflineGuard.is_replay_active()` and raises `ReplayIsolationViolation` if True.
- **Result**: PASS
