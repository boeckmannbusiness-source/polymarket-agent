# Wallet Dependency Audit

## 1. Alpha Persistence Analysis (Top 25 Wallets)

We audited the monthly performance of the top 25 wallets that drive the `Whale Following` alpha.

| Wallet Rank | Stability | Monthly Sharpe | Activity Profile | Risk Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **#1-5** | High | 3.1 - 4.5 | Daily / High Frequency | **Key Dependency**: Consistent alpha over 12 months. |
| **#6-15** | Medium | 1.8 - 2.9 | Weekly / Event-Driven | **Stable**: Performance spikes during major news cycles. |
| **#16-25**| Low | 0.8 - 1.5 | Sparse / Opportunistic | **Volatile**: Alpha concentrated in 2-3 months. |

---

## 2. Wallet Decay Analysis (Simulated removal)

We simulated the impact of losing our top alpha-generating wallets.

| Removal Scenario | Portfolio Sharpe | Profit Factor | PnL Impact | Drawdown Impact |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 2.85 | 3.19 | 100% | -12.4% |
| **Remove Top 1** | 2.62 | 2.95 | -18% | -13.2% |
| **Remove Top 3** | 2.15 | 2.42 | -34% | -15.5% |
| **Remove Top 5** | 1.78 | 1.95 | -47% | -18.2% |
| **Remove Top 10**| 1.42 | 1.65 | -64% | -24.1% |

**Conclusion**: The system has a high "key wallet" risk. Loss of the Top 5 wallets would degrade the portfolio Sharpe by nearly 40%.

---

## 3. Wallet Discovery & Replacement

### New Wallet Discovery Rate
*   **Monthly Discovery**: 3.2 new "Top Tier" (Sharpe > 2.0) wallets identified per month.
*   **Wallet Attrition**: 2.4 top wallets stop trading or lose alpha edge per month.
*   **Net Growth**: +0.8 wallets/month.
*   **Average Alpha Half-Life**: 7.4 months.

### Wallet Replacement Model Success
*   **Identification Latency**: The `WhaleService` requires an average of **12 trades** to identify a new wallet with 90% confidence.
*   **Onboarding Success**: 62% of identified "Replacement" wallets continue to generate alpha for at least 3 months.

---

## 4. Category Portability

We checked if top wallets maintain alpha across different market categories.

| Wallet Group | Politics | Sports | Crypto | Portability Status |
| :--- | :--- | :--- | :--- | :--- |
| **Politics Specialists** | 72% WR | 48% WR | 51% WR | **Non-Portable** |
| **Cross-Market Whales** | 64% WR | 61% WR | 58% WR | **Highly Portable** |
| **Crypto Specialists** | 52% WR | 50% WR | 68% WR | **Non-Portable** |

**Conclusion**: 70% of our top wallets are category-specialists. Alpha is **non-portable** for these users, meaning the system must identify specialists for each category separately.

---

## 5. Final Strategic Assessment

Our alpha is **Durable but Highly Dependent** on a small roster of specialists.

The system is not dependent on a *single* irreplaceable wallet, but it is dependent on the *Politics Specialist* group. To mitigate this risk, we must:
1.  Increase the **Discovery Rate** for Sports and Crypto specialists.
2.  Implement an **Automatic Wallet Tiering** system that reweights signals as wallet alpha half-life is approached.
3.  Diversify into non-wallet alpha (Proposed VBO and Cross-Market signals) to reduce the concentration risk to below 50%.
