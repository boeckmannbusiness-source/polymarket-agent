# CERTIFICATION_EVIDENCE_INDEX

## Objective
Provide a centralized index mapping all safety claims to their corresponding evidence files, automated tests, and implementation locations.

## 1. System Governance & Authorization
| Claim | Evidence File | Test File | Code Location |
|-------|---------------|-----------|---------------|
| Execution is strictly governed by mode and permissions. | `AUTHORIZATION_MATRIX.md` | `backend/app/tests/sandbox/test_execution_governance.py` | `backend/app/services/execution/governance/` |
| System capabilities are explicitly restricted. | `SYSTEM_CAPABILITY_MAP.md` | `backend/app/tests/architecture/test_capability_coverage.py` | `backend/app/services/capabilities/` |

## 2. Execution Determinism & Replay
| Claim | Evidence File | Test File | Code Location |
|-------|---------------|-----------|---------------|
| Execution creates deterministic SHA-256 fingerprints. | `DETERMINISM_PROOF.md` | `backend/app/tests/architecture/test_asset_determinism.py` | `backend/app/services/replay/execution_fingerprint.py` |
| Replay ensures 100% offline simulation parity. | `REPLAY_INTEGRITY_REPORT.md` | `backend/app/tests/architecture/test_replay_determinism.py` | `backend/app/services/replay/` |
| Capital risk decisions are reproducible in replay. | `CAPITAL_REPLAY_PROOF.md` | `backend/app/tests/capital/test_capital_replay.py` | `backend/app/services/capital/replay.py` |

## 3. Runtime Safety Hardening (Sprint 7.1 Closure)
| Claim | Evidence File | Test File | Code Location |
|-------|---------------|-----------|---------------|
| System fails closed if unsafe configuration detected. | `STARTUP_ASSERTION_PROOF.md` | `backend/app/tests/test_startup_safety.py` | `backend/app/services/capabilities/startup_validation.py` |
| Signed artifacts are isolated and non-serializable. | `SIGNED_ARTIFACT_PROOF.md` | `backend/app/tests/test_signed_artifact_boundary.py` | `backend/app/services/wallet/signing_sandbox.py` |
| Safety exceptions propagate and cannot be swallowed. | `EXCEPTION_BOUNDARY_REPORT.md` | `backend/app/tests/architecture/test_exception_boundaries.py` | `backend/app/services/execution/execution_service.py` |
| Guards maintain absolute structural dominance. | `GUARD_DOMINANCE_PROOF.md` | `backend/app/tests/architecture/test_guard_dominance.py` | `backend/app/services/execution/execution_service.py` |

## 4. Risk Governance
| Claim | Evidence File | Test File | Code Location |
|-------|---------------|-----------|---------------|
| Capital deployment is multi-layer blocked. | `RISK_GOVERNANCE_REPORT.md` | `backend/app/tests/capital/test_capital_governance.py` | `backend/app/services/capital/` |

## Conclusion
All claims required for **SANDBOX EXECUTION CERTIFICATION** are supported by explicit evidence files and automated verification proofs.
