# STARTUP_ASSERTION_PROOF

## Objective
Verify that the system enforces critical safety invariants at process startup and fails closed if any unsafe configuration is detected.

## Safety Invariants
The following invariants are validated by `StartupSafetyValidator` before any other system component is initialized:

1.  **EXECUTION_MODE**: Must be one of `SIMULATION` or `SANDBOX`.
2.  **STRICT_LIVE_ENABLED**: Must be `False`.
3.  **CAPITAL_ENABLED**: Must be `False`.

## Verification Results

### Automated Test Proof
The tests in `backend/app/tests/test_startup_safety.py` verify these invariants and the fail-closed behavior.

```bash
PYTHONPATH=backend/ python3 -m pytest backend/app/tests/test_startup_safety.py
```

**Results:**
```text
============================= test session starts ==============================
collected 6 items

backend/app/tests/test_startup_safety.py ......                          [100%]

======================== 6 passed in 0.25s =========================
```

### Test Case Coverage
| Test Case | Description | Result |
|-----------|-------------|--------|
| `test_startup_safety_valid_simulation` | Pass if mode=simulation, live=False, capital=False | **PASSED** |
| `test_startup_safety_valid_sandbox` | Pass if mode=sandbox, live=False, capital=False | **PASSED** |
| `test_startup_safety_invalid_mode` | Fail if mode=live | **PASSED** |
| `test_startup_safety_strict_live_violation` | Fail if STRICT_LIVE_ENABLED=True | **PASSED** |
| `test_startup_safety_capital_enabled_violation` | Fail if CAPITAL_ENABLED=True | **PASSED** |
| `test_main_lifespan_fail_closed` | Verify FastAPI lifespan aborts on violation | **PASSED** |

## Implementation Details
- **Validator Location**: `backend/app/services/capabilities/startup_validation.py`
- **Integration Point**: `backend/app/main.py` at the very start of the `lifespan` function.
- **Exception**: `StartupSafetyViolation` (inherits from `ConfigurationError`).

## Conclusion
The system is structurally incapable of booting into an unsafe configuration (Live mode or Capital enabled) during this certification phase. Any attempt to override these settings via environment variables will result in an immediate process abort.
