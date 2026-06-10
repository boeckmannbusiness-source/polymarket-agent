# Solana/Jupiter Migration Assessment Report

## Section 1 — Reusable Components

The following components are designed as chain-agnostic infrastructure and can be preserved with minimal effort.

| Component Name | Current Responsibility | Migration Effort | Recommended Action |
| :--- | :--- | :--- | :--- |
| **Event Bus** | Redis-based pub/sub and stream management for inter-agent communication. | Zero | **KEEP** |
| **Mode Manager** | Controls system states (Paper, Shadow, Live, Emergency). | Zero | **KEEP** |
| **SafetyService** | Circuit breakers and global kill-switches for system stability. | Low | **KEEP** |
| **MonitoringAgent** | Aggregates health metrics, latencies, and agent status. | Low | **KEEP** |
| **BaseAgent** | Core orchestration logic and lifecycle management for all agents. | Zero | **KEEP** |
| **PostgreSQL DB** | Persistence for signals, trades, and audit logs (logic layer). | Medium | **REFACTOR** (Schema adjustments) |
| **Shadow Framework** | Validates agent decisions against real-time data without execution. | Medium | **REFACTOR** |
| **Alerting Infra** | Telegram notifications and Grafana dashboards for monitoring. | Low | **KEEP_WITH_MINOR_CHANGES** |

---

## Section 2 — Polymarket Dependencies

The current system has deep vertical integration with Polymarket’s CLOB and Gamma APIs. These must be decoupled.

| Dependency | File Locations | Description | Replacement Strategy |
| :--- | :--- | :--- | :--- |
| **Gamma API** | `backend/app/ingesters/polymarket_rest.py` | Market discovery and metadata. | **Replace** with Birdeye/DexScreener API for token discovery. |
| **CLOB API** | `backend/app/exchanges/polymarket_client.py` | Order execution and orderbook data. | **Replace** with Jupiter Swap/Quote API. |
| **Market Schema** | `backend/app/models/market.py`, `backend/app/schemas/market.py` | Fields: `condition_id`, `slug`, `outcomes`, `clob_token_ids`. | **Refactor** to `mint_address`, `pair_address`, `decimals`, `liquidity_source`. |
| **Polygon RPC** | `backend/app/ingesters/polygon_rpc.py` | Log polling for CTF Exchange contracts. | **Replace** with Helius Webhooks for Solana Token Program events. |
| **EIP-712 Signer**| `backend/app/exchanges/polymarket_signer.py`| Ethereum-compatible signing for CLOB orders. | **Replace** with Solana `Keypair` Ed25519 signing. |
| **Binary Logic** | `backend/app/services/trade_service.py` | Assumes YES/NO outcome shares. | **Refactor** to generic token swap (Base -> Quote) logic. |

---

## Section 3 — Jupiter Integration Design

The Jupiter Adapter will serve as the gateway between the `ExecutionAgent` and the Solana network.

### Target Architecture
```text
Market Data Layer (Helius/Birdeye)
        ↓
Signal Layer (Strategy Logic)
        ↓
Risk Layer (Exposure & Wallet Checks)
        ↓
Execution Layer (ExecutionAgent)
        ↓
Jupiter Adapter (Quote -> Sign -> Execute -> Track)
```

### Key Requirements
*   **Quote Support:** Interface with `/quote` to find optimal routing, price impact, and slippage.
*   **Swap Execution:** Interface with `/swap` to retrieve the transaction payload, sign locally, and broadcast.
*   **Position Tracking:** Track "positions" as token balances (e.g., SOL/USDC) rather than contract shares.
*   **Transaction Status Tracking:** Use `getSignatureStatuses` or Helius Webhooks for reliable confirmation tracking.
*   **Fail-Closed Execution:** Validate balance changes post-swap; if a transaction is not confirmed within the TTL, the system enters a recovery state for that position.

---

## Section 4 — Solana Market Data Sources

Evaluating the best-in-class sources for a Solana-native agent.

| Source | Purpose | Reliability | Recommended Usage |
| :--- | :--- | :--- | :--- |
| **Helius** | Webhooks, Transaction Parsing, RPC. | High | Primary source for "on-chain" event detection (swaps, liquidities). |
| **Birdeye** | Token pricing, OHLCV, Whale tracking. | High | Strategy signals (momentum, volume spikes). |
| **Jupiter API** | Quoting, routing, and price impact. | High | Pre-trade validation and execution. |
| **DexScreener** | Token metadata, social links, liquidity. | Medium | Market enrichment and filtering new/unverified tokens. |
| **Solana RPC** | Direct state access (balances, accounts). | High | Final confirmation and wallet balance checks. |

---

## Section 5 — Agent Redesign

### WhaleAgent
*   **Smart money tracking:** Pivot from tracking Polymarket "Whales" (outcome bettors) to Solana "Smart Money" (wallets with high ROI on Raydium/Jupiter).
*   **Wallet clustering:** Implement wallet clustering to detect coordinated "buys" on low-cap tokens.
*   **Copy-trading signals:** Generate signals when multiple high-score wallets enter the same mint within a short window.

### SignalAgent
*   **Momentum:** Detect rapid price increases accompanied by sustained volume.
*   **Volume spikes:** Monitor 5m volume vs 1h average for early entry.
*   **Liquidity shifts:** Track liquidity additions/removals in Raydium pools.
*   **Token rotation:** Logic to detect capital moving between sectors (e.g., SOL -> AI Memes).

### RiskAgent
*   **Evolution:** Unchanged core logic (max position, daily loss), but modified to handle token volatility.
*   **Slippage Guard:** Must strictly enforce maximum price impact via Jupiter quotes before approving a trade request.

### ExecutionAgent
*   **Jupiter Integration:** Replace the Polymarket client with the Jupiter Adapter. Implement "Priority Fees" to ensure execution during high-congestion periods.

---

## Section 6 — Migration Roadmap

### Phase A: Architecture preparation
*   **Objectives:** Update DB schemas, Redis keys, and core Type definitions.
*   **Estimated Complexity:** Low
*   **Risks:** Breaking existing backtest compatibility.
*   **Dependencies:** None

### Phase B: Market data replacement
*   **Objectives:** Integrate Helius/Birdeye feeds into `market:data` stream. Replace Polygon RPC listener.
*   **Estimated Complexity:** Medium
*   **Risks:** API rate limits and data normalization.
*   **Dependencies:** Phase A

### Phase C: Agent adaptation
*   **Objectives:** Refactor Whale and Signal agents for Solana data types. Update strategy logic.
*   **Estimated Complexity:** High
*   **Risks:** Strategy alpha decay (Polymarket alpha ≠ Solana alpha).
*   **Dependencies:** Phase B

### Phase D: Execution layer
*   **Objectives:** Implement Jupiter Adapter and Solana Signer.
*   **Estimated Complexity:** Medium
*   **Risks:** Transaction failure handling in a high-speed env.
*   **Dependencies:** Phase A

### Phase E: Shadow trading on Solana
*   **Objectives:** Run the full pipeline with real data but simulated execution.
*   **Estimated Complexity:** Low
*   **Risks:** False positives in simulated slippage.
*   **Dependencies:** Phase C & Phase D

### Phase F: Micro-capital deployment
*   **Objectives:** Live deployment with < $10 positions to verify e2e flow.
*   **Estimated Complexity:** Medium
*   **Risks:** Smart contract risks or bot front-running.
*   **Dependencies:** Phase E

---

## Success Criteria

1.  **What can be reused:** ~70% of orchestration, safety, and monitoring infra.
2.  **What must be replaced:** Polymarket-specific ingesters, clients, and binary-outcome schemas.
3.  **Estimated migration effort:** ~4-6 weeks for full production readiness.
4.  **Recommended architecture:** Multi-agent stream-processing with Helius/Birdeye input and Jupiter execution.
5.  **Fastest path:** Initial "Shadow Mode" deployment using Birdeye data and Jupiter quoting (approx. 2 weeks).
