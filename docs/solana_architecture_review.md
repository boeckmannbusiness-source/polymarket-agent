# Independent Architecture Review: Solana/Jupiter Migration

**Reviewer:** Jules (Senior Staff Engineer)
**Status:** GO-WITH-CHANGES
**Confidence Level:** 75% (Technical feasibility is high; Alpha feasibility is medium)

---

# Executive Summary

The transition from Polymarket/Polygon to Solana/Jupiter is technically sound in terms of the multi-agent orchestration, but the current proposal underestimates the **infrastructure latency** and **MEV environment** of Solana. While the EventBus and Agent logic can be adapted, the assumption that "Smart Money Tracking" works as simply as it did on Polymarket is likely incorrect due to the high noise-to-signal ratio on Solana.

**Recommendation:** GO-WITH-CHANGES. We should prioritize a "Headless Execution" model and move state management closer to the RPC to survive Solana's volatility.

---

# Top 10 Risks

1.  **RPC Latency & Congestion (Critical):** Using standard RPCs/Webhooks will result in signals that arrive 2-5 seconds after the "Smart Money" has already moved the price.
2.  **MEV & Sandwich Attacks (Critical):** Jupiter execution without Jito bundles exposes the ExecutionAgent to predatory sandwich bots on every trade.
3.  **Data Provider Staleness (High):** Birdeye and DexScreener APIs often lag on-chain reality by 30-60s during high volatility.
4.  **Toxic Flow / Honeypots (High):** Tracking "Smart Money" frequently leads to following developers into honeypots or rugs designed to look like smart wallets.
5.  **State Drift (Medium):** The Redis EventBus introduces an additional 10-50ms of latency which is negligible on Polymarket but significant for Solana memecoin entries.
6.  **Priority Fee Estimation (Medium):** Dynamic priority fee logic is complex; underestimating will lead to dropped transactions, overestimating will kill the ROI of a €25 portfolio.
7.  **Rate Limit Choke (Medium):** The "Free Tier" minimum stack will fail during a "volatility event" (exactly when we want to trade).
8.  **Wallet Security (Low):** Moving from EIP-712 (signed messages) to Ed25519 (raw txn signing) requires extremely strict key management.
9.  **Scale-to-Profitability (Low):** Fixed network fees on Solana may exceed the profit margin on €2 trades (the proposed memecoin limit).
10. **Schema Inflexibility (Low):** The `TokenPosition` model doesn't account for "rugged" tokens that can't be sold, potentially bloating the DB.

---

# Incorrect Assumptions

1.  **"Whale Following is Alpha":** On Solana, most "whales" are actually multi-wallet sybil clusters or bot farms. Tracking them requires advanced clustering, not just ROI scoring.
2.  **"Jupiter is Free":** While Jupiter has 0% fees, the slippage and price impact on mid-caps can be 5-10% in a single transaction.
3.  **"Helius Webhooks are Instant":** Webhooks are subject to internet latency and Helius processing time. For true alpha, we need Geyser/gRPC.
4.  **"Polymarket Logic Preserved":** Polymarket was binary (YES/NO); Solana is continuous. The `RiskAgent` logic for "Stop Loss" on a 50% drawdown is a "Stop Realization" on Solana.

---

# Simplifications

1.  **Remove DexScreener from Core Path:** Use it only for UI enrichment, not for signal generation. It's too slow.
2.  **Postpone Ensemble Strategy:** Start with a single clean "Whale Follow" signal. Ensemble logic adds too much complexity during initial testing.
3.  **Use Jito Bundles exclusively:** Do not build a "standard" transaction sender. Go straight to Jito to avoid MEV.

---

# Revised Architecture Recommendation

To survive Solana, we must move to a **"Direct-to-Geyser"** architecture:

1.  **Geyser Ingester (Replace Webhooks):** Use LaserStream (gRPC) to get transactions the millisecond they are confirmed.
2.  **Local Execution Cache:** The `ExecutionAgent` should maintain a local cache of token balances and prices to avoid "Price Stale" errors from Jupiter.
3.  **Jito-Enabled Execution:** Integrate `jito-searcher-client` to bundle swaps with a tip, ensuring atomic execution and front-run protection.

---

# Revised Roadmap

- **Week 1-2: Data & State (Hardened):** Implement gRPC ingester and the `TokenPosition` schema. Skip Webhooks.
- **Week 3: Wallet Intelligence (Clustering):** Build a basic sybil-detection layer for the `WhaleAgent`.
- **Week 4-5: Jito Execution:** Build the Jupiter + Jito adapter. This is the most critical technical hurdle.
- **Week 6: Shadow Mode (Live Data):** Run 1 week of shadow trading with a focus on "Landed Txn Ratio" and "Realized Slippage."
- **Week 7: Micro-Capital (Launch):** Deploy with €100 total capital.

---

# Final Decision: GO_JUPITER (WITH CHANGES)

Solana is the correct move for autonomy and deployment flexibility, but we must treat it as a **Latency & MEV Game**, not an Alpha-Logic game. If we build the Polymarket architecture on Solana, we will simply be "exit liquidity" for faster bots.
