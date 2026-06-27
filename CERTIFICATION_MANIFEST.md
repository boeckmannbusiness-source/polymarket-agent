# CERTIFICATION_MANIFEST

## Purpose
Single machine-readable source of certification assumptions for Sandbox Execution.

## Safety Invariants

| Invariant | Description |
|-----------|-------------|
| **EXECUTION_MODE** | Must be in {`simulation`, `sandbox`}. `live` is strictly forbidden. |
| **STRICT_LIVE_ENABLED** | Must be `False`. Prevents any transition to live state. |
| **CAPITAL_ENABLED** | Must be `False`. Blocks all capital deployment paths. |
| **Registry Frozen** | `ExchangeAdapterRegistry` must be frozen after bootstrap to prevent rogue adapter injection. |
| **No Broadcast Writer** | No `RpcWriter` implementation used in Sandbox can expose a working `send_transaction` (must raise). |
| **Artifact Isolation** | `SignedArtifact` must forbid serialization (`model_dump`, `model_dump_json`) to prevent persistence. |
| **Replay RPC Guard** | `ReplayOfflineGuard` must prevent all RPC access during replay sessions. |
| **Exception Propagation** | Safety-critical exceptions (`StartupSafetyViolation`, `ExecutionAuthorizationError`, `ReplayIsolationViolation`) must propagate and never be swallowed. |

## Evidence Mapping

| Invariant | Enforcement Component | Proof Document | Test File | Owner Layer |
|-----------|-----------------------|----------------|-----------|-------------|
| **EXECUTION_MODE** | `StartupSafetyValidator` | `STARTUP_ASSERTION_PROOF.md` | `backend/app/tests/test_startup_safety.py` | Capabilities |
| **STRICT_LIVE_ENABLED** | `StartupSafetyValidator` | `STARTUP_ASSERTION_PROOF.md` | `backend/app/tests/test_startup_safety.py` | Capabilities |
| **CAPITAL_ENABLED** | `StartupSafetyValidator` | `STARTUP_ASSERTION_PROOF.md` | `backend/app/tests/test_startup_safety.py` | Capabilities |
| **Registry Frozen** | `ExchangeAdapterRegistry` | `SYSTEM_STATE.md` | `backend/app/tests/architecture/test_registry_immutability.py` | Exchanges |
| **No Broadcast Writer** | `SandboxRpcWriter` | `RPC_READINESS.md` | `backend/app/tests/sandbox/test_execution_governance.py` | RPC |
| **Artifact Isolation** | `SignedArtifact` | `SIGNED_ARTIFACT_PROOF.md` | `backend/app/tests/test_signed_artifact_boundary.py` | Wallet |
| **Replay RPC Guard** | `ReplayOfflineGuard` | `REPLAY_INTEGRITY_REPORT.md` | `backend/app/tests/architecture/test_replay_determinism.py` | Replay |
| **Exception Propagation** | `ExecutionService` | `EXCEPTION_BOUNDARY_REPORT.md` | `backend/app/tests/architecture/test_exception_boundaries.py` | Execution |
| **Guard Dominance** | `CapitalGuard` | `GUARD_DOMINANCE_PROOF.md` | `backend/app/tests/architecture/test_guard_dominance.py` | Capital |
