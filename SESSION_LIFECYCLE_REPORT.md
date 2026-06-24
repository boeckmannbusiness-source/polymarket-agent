# Session Lifecycle Report

## State Transitions
1. **ACTIVE**: Session is created with a 30-minute TTL. Signing is allowed if capabilities permit.
2. **EXPIRED**: Session has passed its `expires_at` time. Signing is invalidated.
3. **DESTROYED**: Key material is wiped from memory. Session cannot be recovered.

## Deterministic Expiration
Expiration is enforced by the `WalletSessionManager` during retrieval.
Expired sessions trigger automatic cleanup of associated key material in the `EphemeralWalletProvider`.

## Verification
`test_wallet_expiration` confirms that expired sessions fail to sign and keys are removed from memory.
