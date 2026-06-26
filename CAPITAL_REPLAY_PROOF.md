# CAPITAL_REPLAY_PROOF.md

## Capital Replay Verification Proof

### Objective
Verify that capital decisions can be replayed offline with 100% fidelity without re-executing risk logic or fetching external state.

### Verification Mechanism
The `CapitalReplay` service validates an `ExecutionTrace` by:
1.  Extracting the `RiskReceipt`.
2.  Verifying the `risk_hash` against the stored `policy_version`, `capital_decision`, `risk_snapshot`, and `reason_codes`.

### Proof of Determinism
Any mutation to the risk snapshot or decision will result in a hash mismatch, invalidating the replay.

### Offline Guarantee
- No RPC calls are made during `CapitalReplay.validate()`.
- No balance lookups are performed.
- Decisions are restored entirely from the `ExecutionTrace`.
