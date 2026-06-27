# SIGNED_ARTIFACT_PROOF

## Objective
Prove that the system maintains a strict boundary for signed artifacts, ensuring that `wallet_signing` does not equate to `broadcast capability` and that signed bytes are never persisted.

## Lifecycle Trace: `SigningSandbox.sign()`
1.  **Generation**: `SigningSandbox.sign_transaction()` calls `EphemeralWalletProvider.sign()`.
2.  **Encapsulation**: The raw signature is wrapped in a `SignedArtifact` domain model.
3.  **Governance**: The `ExecutionGovernor` must explicitly authorize the `SIGN` permission.
4.  **Isolation**: The `SignedArtifact` model explicitly forbids serialization (`model_dump`, `model_dump_json`).
5.  **Policy Enforcement**: `SignedArtifactPolicy` ensures the artifact is transient and prevents export or replay.
6.  **Destruction**: Since the artifact cannot be serialized or persisted, it exists only in transient memory and is destroyed when the Python object is garbage collected or the session expires.

## Safety Questions & Answers

| Question | Answer | Proof Mechanism |
|----------|--------|-----------------|
| **Can signed bytes exist?** | YES | Created transiently within `SigningSandbox`. |
| **Can they escape?** | NO | `SignedArtifact` prevents serialization to strings/JSON/DB. |
| **Can replay access them?** | NO | Not persisted in `ExecutionTrace` or any database. |
| **Can external broadcast occur?** | NO | `SigningSandbox` explicitly forbids `broadcast()` and `send_transaction()`. |

## Automated Test Proof
The tests in `backend/app/tests/test_signed_artifact_boundary.py` verify these isolation properties.

```bash
PYTHONPATH=backend/ python3 -m pytest backend/app/tests/test_signed_artifact_boundary.py
```

**Results:**
```text
============================= test session starts ==============================
collected 4 items

backend/app/tests/test_signed_artifact_boundary.py ....                  [100%]

======================== 4 passed in 0.09s =========================
```

## Implementation Details
- **Domain Model**: `backend/app/domain/wallet/models.py` (`SignedArtifact` with forbidden serialization).
- **Policy Layer**: `backend/app/services/wallet/policy.py` (`SignedArtifactPolicy` enforcing transience).
- **Hardened Service**: `backend/app/services/wallet/signing_sandbox.py` (Returns `SignedArtifact` instead of raw string).

## Conclusion
The signed artifact boundary is structurally enforced. Signed transaction bytes are transient, non-serializable, and isolated from any broadcast-capable component. The possession of a `SignedArtifact` provides zero capability for persistent storage or unauthorized external broadcast.
