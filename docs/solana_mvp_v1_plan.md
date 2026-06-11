# Solana MVP v1 Plan: Research & Shadow Trading

## Objective
Validate the alpha of Smart Wallet tracking on Solana before building execution infrastructure. This phase focuses on data ingestion, wallet intelligence, and shadow PnL tracking.

---

## Architecture Changes

### Data Pipeline
- **Helius Ingester:** Webhook-based ingestion of `onchain_trade` events.
- **Birdeye Enrichment:** API-based enrichment for token prices and metadata.
- **Event Bus:** Normalized Solana events published to `market:data`.

### Agent Pivot
- **SmartWalletAgent (fka WhaleAgent):** Refactored to perform real-time scoring, clustering, and ROI tracking.
- **SignalAgent:** Simplified to output only "Smart Wallet Follow" signals. Ensemble and technical strategies are disabled.
- **ShadowPortfolioService:** New service to simulate trades, track PnL, and evaluate strategy performance without on-chain execution.

---

## Database Changes

### New Models

#### SmartWallet
- `address` (PK, string)
- `sol_balance` (float)
- `win_rate` (float)
- `roi_30d` (float)
- `avg_holding_time` (interval)
- `smart_score` (float)
- `last_active` (datetime)
- `is_cluster_head` (bool)

#### ShadowPosition
- `id` (PK, uuid)
- `mint_address` (string)
- `symbol` (string)
- `entry_price` (float)
- `exit_price` (float, nullable)
- `size_usd` (float)
- `pnl_usd` (float)
- `signal_id` (uuid, FK)
- `wallet_source` (string, FK)
- `status` (string) # open, closed

---

## Agent Changes

| Agent | Action | Responsibility |
| :--- | :--- | :--- |
| **WhaleAgent** | **REFACTOR** | Rename to `SmartWalletAgent`. Implement ROI and Win-Rate scoring logic. |
| **SignalAgent** | **SIMPLIFY** | Disable all technical strategies. Generate signals based exclusively on SmartWallet events. |
| **ExecutionAgent** | **DEACTIVATE** | Replace with `ShadowPortfolioService` for PnL logging. |
| **RiskAgent** | **STAY** | Maintain position limits for shadow trades to ensure realistic PnL simulation. |

---

## Milestones & Effort

### Milestone 1: Data Ingestion (Effort: 3 days)
- [ ] Helius Webhook listener.
- [ ] Birdeye pricing enrichment.
- [ ] Normalization of `market:data` for Solana.

### Milestone 2: Wallet Intelligence (Effort: 5 days)
- [ ] `SmartWalletAgent` ROI calculation logic.
- [ ] Wallet clustering (Sybil detection).
- [ ] Real-time SmartWalletScore updates.

### Milestone 3: Shadow Tracking (Effort: 4 days)
- [ ] `ShadowPortfolioService` implementation.
- [ ] Automated entry/exit logging based on signals.
- [ ] Dashboard integration for Shadow PnL.

### Milestone 4: Alpha Validation (Effort: 2-4 weeks)
- [ ] Observe signal performance.
- [ ] Calculate Sharpe Ratio and Win Rate.
- [ ] Go/No-Go for Phase 2 (Jupiter Execution).

**Total Estimated Effort:** 2 weeks (Engineering) + 4 weeks (Observation).

---

## Success Metric
- **Hypothesis:** "Top 5% of scored wallets generate a cumulative Shadow ROI > 10% over 14 days."
- If the hypothesis is confirmed, we proceed to Phase 2 (Jupiter/Jito/Live).
