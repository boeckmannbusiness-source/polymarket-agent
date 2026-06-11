# Solana Migration Backlog

## Phase A: Architecture Lock (COMPLETED)
- [x] Perform feasibility study.
- [x] Design TokenPosition schema.
- [x] Audit Jupiter APIs.

## Phase B: Infrastructure (Current)
- [ ] Implement Helius Webhook Ingester.
- [ ] Implement Birdeye Data Provider (OHLCV).
- [ ] Add `TokenPosition` and `SolanaWallet` tables to DB.

## Phase C: Agent Logic
- [ ] Refactor `WhaleAgent` for SmartWalletScore v1.
- [ ] Update `SignalAgent` with VolumeSpike and Momentum logic.
- [ ] Port `EnsembleStrategy` to Solana feature vectors.

## Phase D: Execution
- [ ] Develop `JupiterAdapter` (Quote/Swap/Execute).
- [ ] Implement Solana Signer (Local Keypair).
- [ ] Add Transaction Status Tracker.

## Phase E: Validation
- [ ] Run Shadow Mode on Solana for 48 hours.
- [ ] Audit slippage and price impact in Shadow Mode.
- [ ] Verify `failed_swap_recovery` logic.

## Phase F: Deployment
- [ ] Micro-capital live deployment (25€).
- [ ] Scale to 100€ capital.
