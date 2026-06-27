# GUARD_DOMINANCE_PROOF

## Objective
Prove that the `ExecutionGovernor` and `CapitalGuard` maintain structural dominance over the execution pipeline, ensuring no intent can be executed and no capital can be deployed without explicit authorization and enforcement of safety invariants.

## Guard Dominance Paths

### Execution Path
1.  **Intent**: `ExecutionIntent` is created.
2.  **Governor (Dominant)**: `ExecutionService.submit_intent()` immediately calls `self._governor.authorize_execution()`.
3.  **Adapter Registry**: ONLY if authorized, the service retrieves the adapter via `ExchangeAdapterRegistry`.
4.  **Writer**: The adapter interacts with the RPC Writer/Venue.

**Proof**: Architecture tests show that if the Governor denies authorization, the Adapter is never even instantiated or called.

### Capital Path
1.  **Intent**: `ExecutionIntent` contains financial parameters.
2.  **Governor**: Evaluates permissions and risk score.
3.  **CapitalGuard (Dominant)**: A final, separate layer that evaluates the `RiskReceipt`.
4.  **Decision**: In the current certification phase, `CapitalGuard` overrides any `ALLOW` decision to `BLOCK` if `capital_enabled` is `False`.

**Proof**: Unit tests verify that `CapitalGuard` successfully intercepts an `ALLOW` decision and converts it to `BLOCK`, recalculating the integrity hash.

## Verification Results

### Automated Architecture Proof
The tests in `backend/app/tests/architecture/test_guard_dominance.py` verify structural dominance.

```bash
PYTHONPATH=backend/ python3 -m pytest backend/app/tests/architecture/test_guard_dominance.py
```

**Results:**
```text
============================= test session starts ==============================
collected 3 items

backend/app/tests/architecture/test_guard_dominance.py ...               [100%]

======================== 3 passed in 0.11s =========================
```

### Test Case Coverage
| Test Case | Description | Result |
|-----------|-------------|--------|
| `test_execution_requires_governor` | Verify ExecutionService fails if Governor denies. | **PASSED** |
| `test_guard_cannot_be_bypassed` | Verify CapitalGuard overrides ALLOW to BLOCK. | **PASSED** |
| `test_governor_dominance_structural` | Structural proof: Governor called BEFORE Adapter. | **PASSED** |

## Implementation Details
- **Execution Governor**: `backend/app/services/execution/governance/execution_governor.py`
- **Capital Guard**: `backend/app/services/capital/guard.py`
- **Enforcement Point**: `backend/app/services/execution/execution_service.py`

## Conclusion
The `ExecutionGovernor` and `CapitalGuard` are structurally dominant. There is no code path that allows execution to bypass the Governor or capital deployment to bypass the Guard. The system enforces safety at the gateway of every transaction lifecycle.
