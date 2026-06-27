# RESIDUAL RISK REGISTER

## R5 — Adapter Registry Mutability
**Finding**: `ExchangeAdapterRegistry` could theoretically be modified at runtime.
**Current Behavior**: Registry is bootstrap-loaded and then frozen.
**Hardening**: Added `freeze()` method and implemented call at startup in `main.py`.
**Immortality Analysis**:
- **Unfreeze**: There is no `unfreeze()` method in the implementation.
- **Replacement**: The registry is a Class-level singleton; it is not instantiated or managed by a dependency container that could replace it.
- **Reload Paths**: A process reload (e.g., Uvicorn reload) triggers a full process restart, which re-executes `main.py` and calls `freeze()` again before request processing begins. No runtime `importlib.reload` paths exist in the application code.
**Proof**: `backend/app/tests/architecture/test_registry_immutability.py` verifies that runtime registration raises `PermissionError` after startup.

## R6 — Admission Replay Currency
**Finding**: Can replay validate stale `AdmissionReceipt`s?
**Status**: ACCEPTED RISK.
**Behavior**: Replay validates integrity (hash identity) only, not freshness (slot TTL). Freshness is enforced during the planning phase for new executions.
**Hardening**: Added documentation to `AdmissionService`.
**Proof**: `backend/app/tests/architecture/test_residual_hardening.py` confirms that `admit_asset` correctly identifies expired receipts during planning/non-replay paths.

## R8 — Replay RPC Isolation Scope
**Finding**: Can direct RPC instantiation bypass `ReplayOfflineGuard`?
**Status**: SECURED.
**Behavior**: `ReplayOfflineGuard` uses a `ContextVar` that is checked deep within `SolanaRpcReader._post`.
**Hardening**: All RPC calls, regardless of instantiation path, must traverse the guarded `_post` method.
**Proof**: `backend/app/tests/architecture/test_residual_hardening.py` (`test_replay_direct_rpc_blocked`) proves that a manually instantiated `SolanaRpcReader` is still blocked during replay.
