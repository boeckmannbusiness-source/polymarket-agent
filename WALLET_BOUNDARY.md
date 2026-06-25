# Wallet Boundary Definition

## Signing vs. Execution
The system maintains a strict boundary between signing operations and execution/broadcast paths.

- **Signing**: Permitted only within the `SigningSandbox` using ephemeral, in-memory keys.
- **Execution**: All broadcast and transaction submission paths are explicitly forbidden in Sandbox mode.

## Ephemeral Lifecycle
Wallets exist only for the duration of a `WalletSession`.
- Keys are generated at session start.
- Keys are held in-memory by the `EphemeralWalletProvider`.
- Keys are destroyed upon session expiration or explicit termination.

## Forbidden Operations
- Private key export
- Wallet persistence (DB or Filesystem)
- Key restoration
- RPC write operations
