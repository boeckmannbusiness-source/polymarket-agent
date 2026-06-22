# AUTHORIZATION MATRIX

## Execution Modes

| Mode | Build | Replay | Sign | RPC Read | RPC Simulate | RPC Write | Capital |
|------|-------|--------|------|----------|--------------|-----------|---------|
| DISABLED | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SIMULATION | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| SANDBOX | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| LIVE | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

*Note: LIVE mode requires explicit approval (`requires_explicit_approval=True`).*

## Execution Lifecycle & Governance

1. **Signal**: Trading signal detected.
2. **Intent**: Created from signal. `ExecutionGovernor.authorize_execution()` called.
3. **Authorization**: `ExecutionAuthorization` record created and audited.
4. **Quote**: Asset resolution and price retrieval.
5. **Plan**: `TransactionPlan` constructed. `ExecutionGovernor.authorize_execution()` called during building.
6. **Payload**: Deterministic binary payload generated for transaction.
7. **Simulation**: Transaction simulated via `SolanaSimulationAdapter`. `ExecutionGovernor.authorize_simulate()` called.
8. **Sign** (SANDBOX/LIVE): Payload signed by `Signer`. `ExecutionGovernor.authorize_sign()` called.
9. **Receipt**: Simulation receipt or transaction hash produced.

## Governance Enforcement

- **ExecutionGovernor**: Centralized authority for all authorization decisions.
- **RPC Isolation**: `NullRpcWriter` and `SandboxRpcWriter` ensure no accidental broadcasts.
- **Audit Trail**: Every decision is logged as an `ExecutionAuditRecord`.
- **Replay**: `ExecutionAuthorizationSnapshot` stored in `ExecutionTrace` to ensure 100% deterministic replay of governance outcomes.
