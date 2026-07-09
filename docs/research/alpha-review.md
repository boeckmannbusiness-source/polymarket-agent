# Quantitative Alpha Review: Polymarket Intelligence Agent

## Executive Summary
This review analyzes the existing signal generation system of the Polymarket Intelligence Agent. We evaluate 10 active strategies, identifying significant overlaps in momentum-based signals and redundant feature logic. We propose a roadmap for improving predictive power by incorporating cross-market data, social sentiment, and deeper liquidity metrics.

---

## 1. Existing Signal Analysis & Ranking

### Signal Ranking by Expected Usefulness
1.  **Whale Following (High):** Strongest alpha source. Historically profitable wallets are excellent lead indicators in prediction markets.
2.  **Adaptive Meta (High):** Effective because it adjusts logic based on price zones (Crisis, Extreme, Fair), reducing noise in stable markets.
3.  **Spread Compression (Medium-High):** High-precision signal for short-term breakouts in liquid markets.
4.  **Liquidity Vacuum (Medium):** Good for catching "sweep" events where someone is buying/selling aggressively.
5.  **Momentum Spike (Medium):** Traditional but reliable in high-volatility regimes.
6.  **Early Whale Entry (Medium):** Catches smaller "smart" money, though higher noise than following major whales.
7.  **Coordinated Wallets (Medium-Low):** Useful for detecting sybil/coordinated activity but difficult to distinguish from random clusters.
8.  **News Repricing (Medium-Low):** Currently overlaps too much with Momentum Spike; lacks direct news integration.
9.  **Momentum Reversion (Low):** Mean reversion is risky in prediction markets which often trend to 0 or 1.
10. **Ensemble (Meta):** Usefulness depends entirely on the accuracy of the underlying `RegimeService`.

### Feature Usage Matrix
| Feature | Strategies Used In |
| :--- | :--- |
| `current_price` | Adaptive Meta, Momentum Reversion, Spread Compression, etc. |
| `momentum_1h` | Momentum Spike, News Repricing, Adaptive Meta, Momentum Reversion |
| `volume_5m` | Momentum Spike, News Repricing, Liquidity Vacuum, Spread Compression, etc. |
| `spread` | Momentum Spike, Liquidity Vacuum, Spread Compression, Adaptive Meta |
| `wallet_score` | Whale Following, Coordinated Wallets, Early Whale Entry, News Repricing |
| `orderbook_imbalance` | Spread Compression, Adaptive Meta |

---

## 2. Identified Overlaps & Redundancies

### Significant Overlaps
*   **Momentum Spike vs. News Repricing:** Both trigger on `momentum_1h` > threshold and `volume_5m` > `3x volume_1h`. They are functionally identical in the current implementation.
*   **Whale Following vs. Early Whale Entry:** Both monitor `size` and `wallet_score`. Early Whale Entry just uses lower size thresholds and includes a momentum alignment check.

### Redundant Logic
*   **Spread Normalization:** Every strategy manually calculates `spread / current_price`. This should be a centralized feature in `MarketStateSnapshot`.
*   **Volume Spikes:** `volume_5m / (volume_1h / 12)` is calculated repeatedly.

### Weak Predictors
*   **Static Momentum Thresholds:** Using a fixed 3% momentum for all markets is weak. 3% in a "Politics" market is different from 3% in a "Crypto" market.
*   **Single-Wallet Following:** Following a single trade without looking at the wallet's historical performance in *that specific category* (e.g., sports vs. politics).

---

## 3. Missing Features for Predictive Power
1.  **Cross-Market Lead-Lag:** Prices on Polymarket often lag behind Betfair or centralized exchanges (for crypto/sports).
2.  **Orderbook Skew (Depth):** Measuring not just the best bid/ask, but the depth 5-10 cents deep to see where the "walls" are.
3.  **Social Sentiment Volatility:** Rapid increases in Twitter/Telegram mentions of a market's topic often precede price moves.
4.  **Time-to-Expiry Decay:** Price sensitivity increases as the market nears resolution.
5.  **Archetype Performance:** Markets of the same "type" (e.g., "Will [Person] be indicted?") often move in correlation.

---

## 4. Proposed New Alpha Signals

### 1. Cross-Market Lead-Lag Alpha
*   **Logic:** Monitor the spread between Polymarket prices and external price feeds (e.g., Binance for crypto markets, Betfair for sports).
*   **Alpha:** Trigger when Polymarket is >2% misaligned with the "global" price, assuming Polymarket will catch up.
*   **Implementation:** Add `external_price` to `MarketStateSnapshot`; create `CrossMarketStrategy`.

### 2. Liquidity Depth Exhaustion
*   **Logic:** Analyze the ratio of `trade_size` to `depth_at_5_cents`.
*   **Alpha:** If a trade consumes 80% of the available depth within 5 cents, it suggests a "vacuum" that will lead to rapid price gapping.
*   **Implementation:** Enhance `PolymarketWSIngester` to track depth levels; create `DepthExhaustionStrategy`.

### 3. Social Sentiment Divergence
*   **Logic:** Compare 1h price momentum with 1h social sentiment momentum.
*   **Alpha:** If sentiment is surging but price is flat, it's a lead indicator for a "News Repricing" event before it shows up in volume.
*   **Implementation:** Integrate a sentiment analysis service (e.g., via LLM or specialized API); create `SentimentDivergenceStrategy`.

### 4. Multi-Whale Cluster Signal
*   **Logic:** Trigger only when 3+ top-tier wallets (Score > 0.8) enter the same side within 15 minutes.
*   **Alpha:** Significantly higher confidence than single-whale following.
*   **Implementation:** Use Redis to track "Recent Whale Entries"; create `WhaleClusterStrategy`.

### 5. Volatility Breakout (VBO)
*   **Logic:** Trigger when `current_price` moves outside a 2-standard-deviation Bollinger Band calculated on 1-minute intervals.
*   **Alpha:** Identifies the start of a regime shift from "Mean Reverting" to "Momentum".
*   **Implementation:** Add `volatility_sd` to `RegimeService`; create `VolatilityBreakoutStrategy`.

---

## 5. Implementation Roadmap

| Phase | Task | Duration |
| :--- | :--- | :--- |
| **Phase 1: Feature Engineering** | Centralize spread/volume features; add external price feeds. | 1 Week |
| **Phase 2: Depth Tracking** | Update ingesters to handle full orderbook depth instead of just mid-price. | 1 Week |
| **Phase 3: Whale Clustering** | Implement the Redis-based temporal clustering logic. | 4 Days |
| **Phase 4: Signal Implementation** | Build the 5 new strategies and backtest against historical data. | 2 Weeks |
| **Phase 5: Refinement** | Decommission redundant `Momentum Spike` and `News Repricing` in favor of `VBO`. | 3 Days |
