# Alpha Robustness Review

## 1. Regime Stability Analysis

We broke down strategy performance across categories, volatility, liquidity, and time-to-resolution to determine alpha universality.

### Performance by Market Category
| Category | Top Strategy | Win Rate | Profit Factor | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Politics** | Whale Following | 71.2% | 3.85 | Extremely high alpha concentration. |
| **Crypto** | Spread Compression | 58.4% | 2.10 | Alpha driven by arb-like execution. |
| **Sports** | Adaptive Meta | 62.1% | 2.45 | Robust across game cycles. |
| **Economics** | Whale Following | 54.2% | 1.65 | Lower confidence; more noise. |

### Performance by Volatility Regime
| Regime | Strategy | Sharpe | PnL Contribution |
| :--- | :--- | :--- | :--- |
| **Low** | Spread Compression | 3.12 | 42% |
| **Medium** | Whale Following | 2.65 | 38% |
| **High** | Adaptive Meta | 2.44 | 20% |

### Performance by Time-to-Resolution
| Horizon | Win Rate | Profit Factor | Robustness |
| :--- | :--- | :--- | :--- |
| **> 30 Days** | 52.1% | 1.45 | Low (Trend Dependent) |
| **7-30 Days** | 64.2% | 2.85 | High (Intelligence Concentration) |
| **1-7 Days** | 61.8% | 2.40 | High (Volume Driven) |
| **< 24 Hours**| 48.2% | 0.95 | Low (Noise/Whiplash) |

---

## 2. Out-of-Sample (OOS) Validation

We split the historical data into Training (Jan-Jun), Validation (Jul-Aug), and Holdout (Sep).

| Strategy | Train Sharpe | OOS Sharpe | Degradation | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Whale Following** | 2.85 | 2.74 | -3.8% | **Robust** |
| **Adaptive Meta** | 3.44 | 3.12 | -9.3% | **Robust** |
| **Coordinated Wallets**| 2.53 | 1.84 | -27.2% | **Potentially Overfit** |
| **Spread Compression** | 1.88 | 1.72 | -8.5% | **Robust** |
| **Momentum Spike** | 0.15 | -0.45 | -400% | **Failed** |

---

## 3. Alpha Concentration Analysis (Whale Activity)

We analyzed whether alpha comes from broad intelligence or a few "super-whales."

*   **Top 10 Wallets**: Contributed 64% of total alpha in the Whale Following strategy.
*   **Top 25 Wallets**: Contributed 82% of total alpha.
*   **Alpha after removing Top 10**: Sharpe drops from 2.85 to 1.42.
*   **Alpha after removing Top 25**: Sharpe drops to 0.78 (marginal alpha).

**Conclusion**: Alpha is highly concentrated in a small group of exceptional wallets. Robustness depends on these specific participants remaining active.

---

## 4. Strategy Interaction & Portfolio Analysis

We ran simulations enabling/disabling strategies to measure marginal contribution.

| Action | Marginal Sharpe | Marginal Drawdown | Recommendation |
| :--- | :--- | :--- | :--- |
| **+ Whale Following** | +0.85 | -4% | Critical |
| **+ Adaptive Meta** | +0.72 | -6% | Critical (Diversifier) |
| **+ Spread Compression**| +0.34 | -1% | High (Base Income) |
| **+ Momentum Spike** | -0.12 | +8% | Detrimental |

---

## 5. Failure Analysis (The "Losing" Trio)

### Momentum Reversion
*   **Why trades lost**: In prediction markets, price moves are often fundamental (news-driven). "Mean Reverting" against a fundamental shift leads to 100% loss.
*   **Entry Location**: Typically entered too early during a breakout.
*   **Decision**: **Retire**. Logic is fundamentally misaligned with prediction market mechanics.

### Momentum Spike & News Repricing
*   **Why trades lost**: High "slippage-to-alpha" ratio. By the time the spike is detected and confirmed by volume, the majority of the move has happened. The "tail" of the move is often just noise/reversion.
*   **Common Condition**: Triggered during low-liquidity "fakeouts."
*   **Decision**: **Replace** with Volatility Breakout (VBO) strategy.

---

## 6. Final Robustness Assessment

Our alpha is **Genuine but Concentrated**.

The system relies heavily on the **Whale Following** (Politics-concentrated) and **Adaptive Meta** strategies. To ensure survival in live deployment, we must prioritize wallet-based intelligence while using **Spread Compression** to provide a stable, uncorrelated baseline. We should immediately decommission the momentum-based "losing trio" to reduce portfolio variance.
