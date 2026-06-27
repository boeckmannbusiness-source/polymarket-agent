# SANDBOX_CERTIFICATION_PACKAGE.md

## Section 1 — Executive Summary

**Project Goal**: To provide a deterministic, governed, and safe autonomous trading intelligence system for Solana-based prediction markets, prioritized for shadow trading and alpha validation.

**Current State**: The system has completed its Day 7 Architecture Review. All core boundaries for simulation, governance, admission, and replay are implemented and verified.

**Decision**: **READY FOR SANDBOX EXECUTION**

**Explicit Exclusions**:
- **NOT LIVE READY**: The system lacks production-grade error recovery for live blockchain state and does not include live execution adapters.
- **NOT CAPITAL READY**: While capital governance is implemented, the system is designed for $0.00 deployment; no live capital should be entrusted to this version.
- **NOT EXECUTION READY**: The current iteration strictly uses simulated adapters (`JupiterExecutionAdapter`, `SolanaSimulationAdapter`) and forbids real-world broadcast.

---

## Section 2 — Architecture Overview

**High-Level Pipeline**:
Observe → Admit → Plan → Simulate → Govern → Decide

**Components**:
- **Observe**: `SolanaRpcReader` (Read-only blockchain observation).
- **Admit**: `AdmissionService` (Market quality and policy evaluation).
- **Plan**: `Planner` (Quote retrieval and route construction).
- **Simulate**: `SolanaSimulationAdapter` (Pre-flight instruction verification).
- **Govern**: `ExecutionGovernor` & `CapitalGovernor` (Permission and risk scoring).
- **Decide**: `CapitalGuard` (Final decision dominance and blocking).

**Decision Termination**: Decisions stop at the `CapitalGuard` layer, which acts as the ultimate circuit breaker before any result is propagated.

---

## Section 3 — Capability Matrix

| Capability | Status | Enforcement | Evidence |
|------------|--------|-------------|----------|
| **observe_chain** | SUPPORTED | `SolanaRpcReader` | `backend/app/services/rpc/solana_rpc_reader.py` |
| **simulate** | SUPPORTED | `SolanaSimulationAdapter` | `backend/app/services/execution/adapters/solana_simulation_adapter.py` |
| **replay** | SUPPORTED | `ReplayOfflineGuard` | `backend/app/services/replay/offline_guard.py` |
| **wallet_signing** | SUPPORTED | `SigningSandbox` | `backend/app/services/wallet/signing_sandbox.py` |
| **admission** | SUPPORTED | `AdmissionService` | `backend/app/services/admission/admission_service.py` |
| **capital_governance** | SUPPORTED | `CapitalGovernor` | `backend/app/services/capital/governor.py` |
| **execution** | BLOCKED | `ExecutionGovernor` | `backend/app/services/execution/governance/execution_governor.py` |
| **broadcast** | BLOCKED | `NullRpcWriter` | `backend/app/services/rpc/null_rpc_writer.py` |
| **capital_deployment** | BLOCKED | `CapitalGuard` | `backend/app/services/capital/guard.py` |

---

## Section 4 — Trust Boundaries

| Boundary | Enforcement | Blocking Layer | Failure Mode |
|----------|-------------|----------------|--------------|
| **Simulation ≠ Execution** | `ExecutionGovernor` | Policy-based Permission Check | `ExecutionAuthorizationError` raised if mode is not LIVE. |
| **Wallet ≠ Broadcast** | `SigningSandbox` | Interface Isolation | `PermissionError` on `send_transaction` or `broadcast` calls. |
| **Admission ≠ Planning** | `Planner.plan()` | Sequential execution | `ValueError` raised if asset is not admitted, halting the plan. |
| **Capital ≠ Allocation** | `CapitalGuard` | Decision Overwrite | `RiskReceipt.capital_decision` forced to `BLOCK`. |
| **Replay ≠ RPC** | `ReplayOfflineGuard` | Context-aware RPC blocking | `ReplayIsolationViolation` on any network attempt during replay. |

---

## Section 5 — Determinism Proof

**Summarized Artifacts**:
- **SimulationReceipt**: Captures `compute_units`, `account_state_hash`, and `slot`.
- **AdmissionReceipt**: Captures market quality metrics and policy version.
- **RiskReceipt**: Captures policy constraints and exposure snapshots.
- **ExecutionTrace**: Aggregates all receipts, intent, and plan into a single verifiable bundle.

**Hash Inputs**: All receipts use SHA-256 fingerprints of their internal state and the associated transaction payload to ensure immutability.

**Replay Mechanism**: `ReplayEngine` restores state from `ExecutionTrace` and re-calculates fingerprints. If fingerprints do not match the original execution, the replay is invalidated.

**Forbidden Dependencies**:
- System clock (replaced by timestamp buckets).
- Randomness (replaced by `ReplaySeed`).
- RPC refresh (blocked by `ReplayOfflineGuard`).

---

## Section 6 — Safety Proof

**Execution Prevention**:
Real-world execution is impossible because:
1. **Blocking Classes**: `NullRpcWriter` and `SandboxRpcWriter` do not implement broadcast logic; they only raise exceptions.
2. **Disabled Capabilities**: The `ExchangeAdapterRegistry` contains no "Live" adapters.
3. **Forbidden Interfaces**: The system lacks any `RpcWriter` implementation capable of calling `sendTransaction` or `broadcast`.
4. **No Balance Mutation**: `CapitalGuard` prevents any trade from reaching an "Allow" state that would trigger balance updates.

---

## Section 7 — Governance Proof

**Governance Chain**:
Admission (Eligibility) → Simulation (Validity) → Capital (Risk) → Guard (Safety) → Decision

**Final Authority**: `CapitalGuard` has absolute dominance. It evaluates the `RiskReceipt` and enforces the global `capital_enabled = False` invariant.

**Override Rules**: `CapitalGuard` can only override a decision from `ALLOW`/`LIMIT` to `BLOCK`. It cannot upgrade a `BLOCK` decision from an earlier layer.

---

## Section 8 — Threat Model

| Scenario | Likelihood | Impact | Mitigation | Residual Risk |
|----------|------------|--------|------------|---------------|
| Hidden execution path | Low | Critical | Governance gated at `ExecutionService` entry. | Low - code review required. |
| Stale admission | Medium | Low | `AdmissionReceipt` includes `valid_until_slot`. | Minimal. |
| Replay corruption | Low | Low | SHA-256 fingerprinting on all traces. | Negligible. |
| Capability escalation | Low | High | `ExecutionGovernor` uses immutable policies. | Low. |
| Wallet persistence | Medium | Medium | `EphemeralWalletProvider` uses in-memory storage only. | Risk of memory dump. |
| RPC Mock Injection | Low | Medium | `ReplayOfflineGuard` blocks at the lowest POST level. | Low. |
| Policy Tampering | Low | High | `RiskReceipt` includes `policy_version` and `risk_hash`. | Medium. |
| Instruction Collision | Low | Low | `ExecutionFingerprint` includes full instruction trace. | Negligible. |
| Account state drift | High | Low | `SimulationReceipt` includes `account_state_hash`. | Expected behavior. |
| Slot Drift | High | Low | `SimulationValidator` enforces 10-slot threshold. | Operational friction. |

---

## Section 9 — Open Risks

**Architecture Drift**:
- **Simulation Coupling**: Architecture tests identified that `SimulationValidator` and `ChainSimulationService` have minor imports from `domain.solana.models`. While this doesn't break safety, it indicates a leak of blockchain-specific types into the simulation service layer.
- **Mock Reliance**: Much of the high-level evidence relies on the correctness of `ExecutionGovernor` and `CapitalGuard` implementation.

---

## Section 10 — Evidence Index

| Claim | Source Document |
|-------|-----------------|
| Replay is deterministic | `DETERMINISM_PROOF.md`, `REPLAY_INTEGRITY_REPORT.md` |
| Capital decisions are replayed offline | `CAPITAL_REPLAY_PROOF.md` |
| Asset resolution is deterministic | `DETERMINISM_PROOF.md` |
| Boundaries are enforced | `AUTHORIZATION_MATRIX.md`, `SYSTEM_CAPABILITY_MAP.md` |
| Simulation is instruction-aware | `CHAIN_SIMULATION_REPORT.md`, `SIMULATION_REALITY_REPORT.md` |
| Risk is governed | `RISK_GOVERNANCE_REPORT.md`, `CAPITAL_POLICY.md` |

---

## Final Section — Certification

**Certification Decision**: **READY FOR SANDBOX EXECUTION**

**Confidence**: **High** (Based on 150+ architecture and integrity tests).

**Constraints**:
- Capital remains **OFF**.
- Broadcast remains **DISABLED**.
- Replay remains **OFFLINE**.
- Unknown assets remain **RESTRICTED**.
- Execution remains **UNAVAILABLE**.

**Required Operating Conditions**:
1. `EXECUTION_MODE` set to `simulation` or `sandbox`.
2. `STRICT_LIVE_ENABLED` set to `False`.
3. `capital_enabled` set to `False`.
