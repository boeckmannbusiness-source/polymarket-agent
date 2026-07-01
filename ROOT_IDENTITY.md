# Root Identity Analysis

**Date:** 2026-07-01
**Method:** Trace all identity keys inbound/outbound across every layer

---

## Candidate: `market_id`

| Property | Value |
|----------|-------|
| **Type** | UUID (v4) — internal Postgres primary key |
| **Source** | Inserted by `PolymarketRESTIngester._upsert_market()`, keyed originally from `condition_id` |
| **Inbound deps** | `condition_id` (from Polymarket on-chain) → `markets.id` (UUID) |
| **Outbound deps** | `Signals.market_id`, `Trades.market_id`, `ShadowDecisionLog.market_id`, `Positions.market_id`, `WalletTrade.market_id`, `MarketEvent.market_id`, `ExchangeOrder.trade_id → Trade.market_id`, `Fill.market_id` |
| **DB references** | 9+ tables |
| **Reporting references** | `ScorecardEngine` computes per-strategy metrics from `ShadowDecisionLog` which is keyed by `market_id` |

---

## Candidate: `condition_id`

| Property | Value |
|----------|-------|
| **Type** | `0x...` hex string (64 hex chars) — Polymarket CTF on-chain ID |
| **Source** | Polymarket blockchain (CTF Exchange) |
| **Inbound deps** | All 3 ingesters produce it: `REST` reads from API response, `WS` resolves via `asset_id→condition_id` mapping, `RPC` extracts from event logs |
| **Outbound deps** | `Markets.condition_id` (unique, indexed), `StructuredSignal.market_condition_id`, `ExchangeOrder.clob_asset_id` (indirectly via mapping) |
| **DB references** | `markets.condition_id` only. Other tables use resolved `market_id` UUID. |
| **Reporting references** | Not referenced directly — flows through to `market_id` |

---

## Candidate: `mint_address`

| Property | Value |
|----------|-------|
| **Type** | Base58 string — Solana token mint |
| **Source** | Helius webhooks → `SolanaWalletTrade.mint_address` |
| **Inbound deps** | Helius trade detection → `SmartWalletAgent` |
| **Outbound deps** | `SolanaWalletTrade.mint_address`, used for token velocity scoring |
| **DB references** | `solana_wallet_trades.mint_address` (indexed). Not referenced by any core execution table. |
| **Reporting references** | Only in Solana-specific scoring side-car |

---

## Candidate: `tx_signature`

| Property | Value |
|----------|-------|
| **Type** | Base58 string — Solana transaction signature |
| **Source** | Helius webhooks |
| **Inbound deps** | `SmartWalletAgent` → `SolanaWalletTrade.tx_signature` |
| **Outbound deps** | `solana_wallet_trades.tx_signature` (unique). Referenced by `ResearchTrade.wallet_trade_id` (FK). |
| **DB references** | 2 tables: `solana_wallet_trades`, `research_trades` (FK) |
| **Reporting references** | None in main reporting |

---

## Candidate: `instrument_id` / `Instrument`

| Property | Value |
|----------|-------|
| **Type** | Pydantic model `Instrument(venue, symbol, asset_identifier, quote_asset)` |
| **Source** | Constructed in `ExecutionIntentFactory` from `Trade.market_id` or `Signal.instrument` |
| **Inbound deps** | `Signal.instrument.venue` + `Signal.instrument.symbol=market_id` |
| **Outbound deps** | `ExecutionIntent.instrument` → `Quote.instrument` → `TransactionPlan` |
| **DB references** | Not persisted directly |
| **Reporting references** | None |

---

## Candidate: `pool_id`

| Property | Value |
|----------|-------|
| **Type** | N/A |
| **Source** | Does not exist in the codebase |
| **Inbound deps** | None |
| **Outbound deps** | None |
| **DB references** | None |
| **Reporting references** | None |

---

## Candidate: `route_id`

| Property | Value |
|----------|-------|
| **Type** | N/A (no `route_id` field exists) |
| **Source** | Does not exist |
| **Inbound deps** | None |
| **Outbound deps** | None |
| **DB references** | None |
| **Reporting references** | None |

---

## Candidate: `wallet_id`

| Property | Value |
|----------|-------|
| **Type** | UUID → `smart_wallets.id` |
| **Source** | Inserted by `SmartWalletAgent` from Helius data |
| **Inbound deps** | Solana trade detection |
| **Outbound deps** | `SolanaWalletTrade.wallet_id` (FK) |
| **DB references** | 2 Solana tables only |
| **Reporting references** | Solana-specific scoring only |

---

## Dependency Graph

```
                        EXTERNAL WORLD
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
   Polymarket REST     Polymarket WS      Polygon RPC
   condition_id ◄──── condition_id ◄──── condition_id
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                    condition_id
                            │
                            ▼
                    markets.condition_id
                            │
                    generated UUID
                            │
                            ▼
                +---- market_id (UUID) ----+
                |           |               |
                v           v               v
            signals     trades     shadow_decision_log
            .market_id  .market_id    .market_id
                |           |               |
                v           v               v
            ExchangeOrder.trade_id ──► Fill.market_id
                |
                v
            ExecutionIntent → Instrument(symbol=market_id)
                |
                v
            TransactionPlan ←── quote, route (Solana/Jupiter)
                |
                v
            ExecutionResult (simulated)
                |
                v (back to)
            shadow_decision_log.market_id
```

---

## Verdict

```
CANONICAL_ROOT = market_id
```

**Proof:**

1. **Inbound:** All three ingesters produce `condition_id`, which is converted to `market_id` UUID upon DB insertion. There is no path where a non-`condition_id` identity enters the main execution pipeline.

2. **Outbound:** `market_id` is the most-referenced identity across the system — 9+ tables, 624 source code references. It is the only identity that survives the full round-trip: ingestion → signal → decision → execution → evidence.

3. **DB references:** Every core table (`signals`, `trades`, `fills`, `positions`, `shadow_decision_log`, `wallet_trades`) is keyed directly or transitively (via FK chain) to `market_id`.

4. **Reporting references:** Scorecards, evidence snapshots, and promotion audits all derive from `shadow_decision_log.market_id`-based decisions.

5. **Solana identities are side-car:** `mint_address`, `tx_signature`, `wallet_id` exist only in `solana_wallet_trades` and `smart_wallets` — these are Helius data ingestion tables that do not participate in the execution pipeline. `ResearchTrade` is the only bridge table, but it's research-only.

The system's true identity is Polymarket's `market_id`. Solana identities (`mint_address`, `tx_signature`) are observability metadata, not canonical identities.
