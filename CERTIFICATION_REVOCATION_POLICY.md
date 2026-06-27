# CERTIFICATION_REVOCATION_POLICY

## Purpose
Define the events, detection mechanisms, and remediation processes for the Sandbox Execution Certification lifecycle.

## 1. Revocation Events
The following events automatically and immediately revoke Sandbox Certification:

| Event | Description | Detection Mechanism |
|-------|-------------|---------------------|
| **Live Adapter Introduction** | Any `ExchangeAdapter` registered that communicates with a live mainnet venue. | `test_certification_drift.py` |
| **Startup Validator Removal** | Removal or neutralization of `StartupSafetyValidator` in `main.py`. | CI Gate / Drift Detector |
| **Capital Enablement** | `CAPITAL_ENABLED` set to `True` in any environment or bypass of `CapitalGuard`. | `test_guard_dominance.py` |
| **Replay RPC Leak** | Replay session successfully performing an RPC call without raising `ReplayIsolationViolation`. | `test_replay_determinism.py` |
| **Artifact Persistence** | `SignedArtifact` successfully serialized to JSON or dict. | `test_signed_artifact_boundary.py` |
| **Safety Exception Swallow** | Broad `except Exception` blocks catching and neutralizing `ExecutionAuthorizationError` or `StartupSafetyViolation`. | `test_exception_boundaries.py` |
| **Registry Defrost** | Modification of `ExchangeAdapterRegistry` after `freeze()` has been called. | `test_registry_immutability.py` |

## 2. Detection Mechanism
- **CI Enforcement**: The `sandbox_certification.yml` workflow runs on every PR. Any failure in the "Certification Gate" steps constitutes a revocation event.
- **Architectural Drift Detector**: Automated tests in `backend/app/tests/certification/` specifically target certification assumptions.
- **Manual Audit**: Periodic review of `ARCHITECTURE_SNAPSHOT.json` against the `CERTIFICATION_MANIFEST.md`.

## 3. Remediation Process
Upon revocation, the following steps must be taken:

1. **Immediate Halt**: All sandbox execution activities must cease.
2. **Root Cause Analysis**: Identify the commit or configuration change that triggered the revocation.
3. **Revert/Fix**: Revert the offending change or implement a fix that restores the safety invariant.
4. **Verification**: Run the full `sandbox_certification` suite locally.
5. **Recertification**: Submit a "Certification Restoration" PR that includes:
   - Proof of fix.
   - Updated evidence documents if applicable.
   - Successful CI run of the certification gate.

## 4. Recertification Evidence
Recertification requires 100% pass rate on:
- `backend/app/tests/architecture/`
- `backend/app/tests/certification/`
- `backend/app/tests/sandbox/`
- `backend/app/tests/test_startup_safety.py`
