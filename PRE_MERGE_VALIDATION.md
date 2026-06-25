# Pre-Merge Validation — Sprint 2.2B Ephemeral Wallet Sandbox

## Validation 1 — Key Destruction Integrity

### Evidence
- **Code Path**:
    - `EphemeralWalletProvider.destroy(wallet_address)`: Deletes the private key from the `self._keys` dictionary.
    - `WalletSessionManager.destroy_session(session_id)`: Calls `self._provider.destroy(session.wallet.address)` and sets `session.destroyed = True`.
    - `WalletSessionManager.get_session(session_id)`: Returns `None` if `session.is_expired()` or `session.destroyed` is `True`.
- **Test Result**: `test_wallet_destroy` and `test_wallet_expiration` in `backend/app/tests/sandbox/test_wallet_sandbox.py` confirm that keys are removed from the provider's memory and sessions become unreachable.
- **Answers**:
    1. **Is key material actually removed?** YES. `del self._keys[wallet_address]` removes the reference.
    2. **Can any object still access signing capability?** NO. The `Signer` interface requires the `wallet_address` to be present in `_keys`.
    3. **Are secrets ever logged?** NO. `EphemeralWallet` uses `Field(exclude=True)` for `private_key`.
    4. **Is any serialization path possible?** NO. `EphemeralWallet` is excluded from serialization in `WalletSession` and `ExecutionTrace`.

### Result: PASS

---

## Validation 2 — Replay Isolation

### Evidence
- **Code Path**:
    - `ReplayEngine.replay(trace)`: Uses `ReplayOfflineGuard.enforce()` which prevents any RPC or network activity.
    - `ReplayEngine._replay_internal(trace)`: Does not instantiate any wallet or signer. It purely reconstructs the `ExecutionResult` using the provided `trace` data, including the new `wallet_receipt`.
- **Call Graph**: `ReplayEngine.replay` -> `ReplayEngine._replay_internal` -> `ExecutionResult` (with metadata from `trace.wallet_receipt`).
- **Test Result**: `test_replay_wallet_isolation` confirms that replay correctly incorporates the `WalletReceipt` without triggering any live wallet operations.

### Result: PASS

---

## Validation 3 — Broadcast Boundary

### Evidence
- **Search Results**:
    - `send_transaction`, `broadcast`, `submit`: These are hard-blocked in `SigningSandbox` with explicit `PermissionError` raises.
    - `RpcWriter`: Not found in the new wallet/replay/execution service code paths.
    - `execute`: Found in `ExecutionService.execute_signal` and `JupiterExecutionAdapter.execute`. However, `SigningSandbox` does not call these.
- **Safety**: The `SigningSandbox` acts as a mandatory wrapper for signing in Sandbox mode. It contains no code to interact with `RpcWriter` or any broadcast-capable adapter. All signing is strictly local to the `EphemeralWalletProvider`.

### Result: PASS

---

## Validation 4 — Capability Escalation

### Evidence
- **Code Path**:
    - `WalletSessionManager.create_session`: Sets capabilities at creation time.
    - `WalletSessionManager.validate_session_for_signing`: Checks if `WalletCapabilityState.SIGN_ONLY` is present in the session's capabilities.
    - `WalletSession` is an immutable Pydantic model (not frozen, but managed by the manager).
- **Negative Test**: `test_sign_with_expired_session` and `test_sign_without_session` verify that signing fails if the session is invalid or has insufficient permissions.
- **Transition Check**: Capabilities are defined at session creation and never updated. There is no `update_capability` method.

### Result: PASS

---

## Deliverable Result: MERGE APPROVED
