# Solana Migration Backlog (Revised: Research-First)

## Phase 1: Infrastructure & Data (MVP v1)
- [ ] **Data Ingestion:** Helius Webhook listener for token swaps.
- [ ] **Market Enrichment:** Birdeye API integration for real-time pricing.
- [ ] **DB Schema:** Deploy `SmartWallet` and `ShadowPosition` models.
- [ ] **Wallet Intelligence:** Refactor `WhaleAgent` into `SmartWalletAgent` with ROI/Win-Rate logic.
- [ ] **Signal Generation:** Configure `SignalAgent` for Smart Wallet Following.
- [ ] **Shadow Trading:** Implement `ShadowPortfolioService` for PnL tracking.

## Phase 2: Alpha Validation (MVP v1)
- [ ] Run Shadow Mode for 14-28 days.
- [ ] Perform audit of signal profitability and wallet score effectiveness.
- [ ] Determine Go/No-Go for live execution.

## Phase 3: Execution Infrastructure (Deferred)
- [ ] **Jupiter Adapter:** Implement Quote/Swap/Execute flow.
- [ ] **Solana Signer:** Local Ed25519 key management.
- [ ] **Jito Integration:** Bundle swaps with tips for MEV protection.
- [ ] **Priority Fees:** Dynamic fee estimation for congestion handling.
- [ ] **Recovery:** Transaction confirmation and failed swap recovery.

## Phase 4: Deployment
- [ ] Micro-capital live deployment (25€-100€).
- [ ] Scaling based on performance.
