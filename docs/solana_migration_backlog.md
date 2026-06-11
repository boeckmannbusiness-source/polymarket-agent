# Solana Migration Backlog (Revised: Data-Centric)

## Phase 1: Infrastructure & Research (MVP v1)
- [ ] **Data Ingestion:** Helius Webhook listener for token swaps.
- [ ] **Market Enrichment:** Birdeye API for pricing and metadata.
- [ ] **Discovery:** Implement `WalletDiscoveryService` to find candidate wallets.
- [ ] **Dataset:** Deploy `ResearchTrade` model to log wallet activity ground-truth.
- [ ] **Shadow Trading:** Implement `ShadowPortfolioService` with simulated costs (1.5% net).
- [ ] **Metrics:** Develop Alpha Validation Dashboard with Profit Factor and Concentration KPIs.

## Phase 2: Alpha Validation Gate
- [ ] Accumulate 100+ shadow trades.
- [ ] Evaluation against Benchmarks (Net ROI > 0, Win Rate > 55%, Profit Factor > 1.2).
- [ ] Wallet Concentration Audit (< 25% from top wallet).
- [ ] Go/No-Go Decision for Live Execution.

## Phase 3: Execution Infrastructure (Deferred)
- [ ] **Jupiter Adapter:** Implement Quote/Swap/Execute flow.
- [ ] **Jito Integration:** Bundle swaps with tips for MEV protection.
- [ ] **Solana Signer:** Local Ed25519 key management.
- [ ] **Clustering:** Advanced Sybil detection and wallet clustering.

## Phase 4: Deployment
- [ ] Micro-capital live deployment (25€-100€).
