# Solana Migration Backlog (Revised: Research-First)

## Phase 1: Infrastructure & Alpha Validation (MVP v1)
- [ ] **Data Ingestion:** Helius Webhook listener for on-chain swaps.
- [ ] **Market Enrichment:** Birdeye API for real-time pricing and token data.
- [ ] **DB Schema:** Deploy `SmartWallet` and `ShadowPosition` models.
- [ ] **SmartWalletAgent:** Refactor to track metrics (ROI, Win Rate, Activity) and score wallets.
- [ ] **Signal Generation:** Configure `SignalAgent` exclusively for Smart Wallet Following.
- [ ] **Shadow Trading:** Implement `ShadowPortfolioService` with deterministic exit logic (TP/SL/Time).
- [ ] **Alpha Validation:** Accumulate 100+ trades and evaluate against success benchmarks.

## Phase 2: Execution & Advanced Intelligence (Deferred)
- [ ] **Wallet Clustering:** Sybil detection and cluster-based scoring.
- [ ] **Jupiter Adapter:** Implement Quote/Swap/Execute flow.
- [ ] **Solana Signer:** Local Ed25519 key management.
- [ ] **Jito Integration:** Bundle swaps with tips for MEV protection.
- [ ] **Priority Fees:** Dynamic fee estimation for congestion handling.
- [ ] **Advanced Strategies:** Re-enable Momentum Spike, Liquidity Vacuum, etc.

## Phase 3: Deployment
- [ ] Micro-capital live deployment (25€-100€).
- [ ] Performance-based scaling.
