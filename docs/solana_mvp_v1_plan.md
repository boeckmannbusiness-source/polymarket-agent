# Solana MVP v1 Plan: Alpha Research Platform (Data-Centric)

## Objective
Determine whether Solana "Smart Money" activity can generate profitable shadow trades. MVP v1 is a research platform designed to collect evidence and validate alpha before any execution infrastructure is built.

---

## Architecture Changes (Evidence-Driven)

### Data Pipeline
- **Helius Ingester:** Webhook-based ingestion of `onchain_trade` events.
- **Birdeye Enrichment:** Real-time pricing and token metadata enrichment.
- **WalletDiscoveryService (NEW):** Identifies candidate wallets based on swap volume, early entry into trending tokens, and repeated success.

### Signal & Research Flow
1. **Wallet Event** → **ResearchTrade Table** (Logs every action for ground-truth).
2. **ResearchTrade** → **Shadow Trade** (Simulated entry/exit).
3. **Outcome** → **Wallet Statistics** (Win Rate, ROI).
4. **Wallet Statistics** → **ResearchScore** (Activity + Recent Success).

### Agent Pivot
- **SmartWalletAgent:** Collects evidence and updates `ResearchScore`. Does NOT block signals for new wallets (solves cold-start).
- **ShadowPortfolioService:** Simulates trades with **real-world cost assumptions** (1% slippage, 0.5% fees).
- **ExecutionAgent:** Deactivated.

---

## Database Changes

### New Models

#### ResearchTrade (The Ground-Truth Dataset)
- `id` (PK, uuid)
- `wallet_address` (string)
- `mint_address` (string)
- `timestamp` (datetime)
- `price_at_detection` (float)
- `price_1h`, `price_6h`, `price_24h`, `price_72h` (float, nullable)
- `return_1h`, `return_6h`, `return_24h`, `return_72h` (float, nullable)

#### ShadowPosition (Net PnL Focused)
- `id` (PK, uuid)
- `mint_address` (string)
- `entry_timestamp` (datetime)
- `entry_price_usd` (float)
- `exit_price_usd` (float, nullable)
- `size_usd` (float)
- `gross_pnl_usd` (float)
- `net_pnl_usd` (float) # After 1% slippage + 0.5% fees
- `status` (string) # open, closed

---

## Simplified Scoring: ResearchScore

To avoid cold-start complexity, use an intentionally simple formula for MVP v1:
`ResearchScore = ActivityScore + RecentSuccessScore`

---

## Shadow Portfolio: Cost Simulation & Exits

Every shadow trade assumes:
- **Slippage:** 1.0%
- **Execution Fees:** 0.5%
- **TP/SL Rules:** +25% Take Profit / -15% Stop Loss / 72h Max Hold.

---

## Alpha Validation Dashboard KPIs
- **Dataset Size:** Total ResearchTrades collected.
- **Wallet Universe:** Count of Observed vs. Active wallets.
- **Net ROI:** Principal-adjusted return after simulated costs.
- **Profit Factor:** Gross Profit / Gross Loss.
- **Concentration:** % of profit contributed by top 10 wallets (limit < 25%).
- **Signal Frequency:** Trades per day/hour.

---

## Phase 2 Go / No-Go Gate

Phase 2 (Jupiter/Jito Execution) may **only** proceed if:
1. **100+** completed shadow trades.
2. **Net ROI > 0** (after slippage and fees).
3. **Profit Factor > 1.2**.
4. **Win Rate > 55%**.
5. **No wallet** contributes > 25% of total profits.

---

## Timeline & Milestones
- **Week 1: Discovery & Ingestion:** Helius/Birdeye integration and `WalletDiscoveryService`.
- **Week 2: Data Collection:** Deploy `ResearchTrade` and `ShadowPosition` models.
- **Week 3-5: Observation Phase:** Collect 100+ trades and monitor Dashboard KPIs.
- **Week 6: Final Audit:** Go/No-Go decision for Phase 2.
