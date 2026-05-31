# Quantitative Operator Audit: Dashboard Specification

This document provides a "ruthless" audit of the production dashboard specification from the perspective of a quantitative trading operator and a Portfolio Manager (PM).

## 1. Metric Actionability & Ranking

The goal is to compress information and maximize signal density.

| Widget | Actionable? | Frequency | Decision Influence | Confidence Risk | Rank |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Daily PnL** | No | 1x/Day | High (Emotional/Context) | Moderate | **Important** |
| **Equity Curve** | No | 1x/Day | High (Trend analysis) | Low | **Critical** |
| **Utilization %** | **Yes** | Constant | **High** (Kill-switch/Scale) | Low | **Critical** |
| **Current Drawdown**| **Yes** | Constant | **High** (Risk-off trigger) | Low | **Critical** |
| **Strategy Attr.** | **Yes** | 1x/Day | **High** (Strategy rotation) | High (Recency bias)| **Critical** |
| **Max VaR** | No | 1x/Day | Moderate (Bounds check) | High (Model risk) | **Important** |
| **Trade Table** | No | low | Low (Micro-monitoring) | High (Over-trading) | **Nice to Have**|
| **Agent Health** | **Yes** | Constant | **Critical** (System halt) | Low | **Critical** |
| **NLV** | No | 1x/Day | Low (Status only) | Low | **Important** |

### Removed as "Noise":
- **Total Return:** Vanity metric; Daily/Weekly velocity is what matters for active oversight.
- **Latency Monitor:** Engineering metric. If it impacts PnL, it shows up in "Execution Attribution". Otherwise, it's noise for a PM.

---

## 2. Performance Attribution: The "Why" Analysis

Current attribution is missing the "Why". To answer **"Why is my portfolio up/down today?"**, we must move from *descriptive* to *diagnostic* metrics.

### Missing Components for Diagnostic Clarity:
1. **Selection vs. Market Attribution:** Did we make money because the market moved (Beta) or because our signals were right (Alpha)?
2. **Execution Slippage:** Did we lose money because of bad entries or high market impact?
3. **Correlation Risk:** Are all our active strategies currently betting on the same outcome (e.g., all long crypto-native)?

### Proposed "Minimum Additions":
- **Alpha vs. Beta Chart:** Overlay the equity curve with a market benchmark (e.g., Polymarket Volume Index).
- **Slippage Impact Metric:** Display total USD lost to slippage/fees vs. gross profit.
- **Exposure Heatmap (by Market):** Shows concentration risk across correlated markets.

---

## 3. The 30-Second PM Workflow

A PM overseeing an autonomous system follows a "Negative Selection" workflow: they look for reasons to *stop* the system, not reasons to praise it.

### The PM's 30-Second Sequence:
1. **Seconds 0-5 (The Shock):** Daily PnL + Equity Curve. "Is the trend broken?"
2. **Seconds 5-15 (The Safety):** Drawdown + Utilization + Health. "Is the system safe and running?"
3. **Seconds 15-30 (The Logic):** Alpha Attribution. "Are the wins/losses coming from the expected strategies?"

### Redesigned "PM-First" Layout:

```text
[ HEADER: DAILY PNL ($/%) | EQUITY CURVE (7D Area) | CURRENT DD% | SYSTEM HEALTH ]
--------------------------------------------------------------------------------
[ SECTION 1: RISK & SAFETY (CRITICAL)                                          ]
[ Utilization Gauge | VaR vs Limit | Max Exposure Market | Kill Switch (Red)   ]
--------------------------------------------------------------------------------
[ SECTION 2: WHY DID WE MAKE/LOSE MONEY? (DIAGNOSTIC)                          ]
[ Top Strategy: [#####] (+$X) | Top Market: [####] (+$Y) | Slippage: [##] (-$Z)]
--------------------------------------------------------------------------------
[ SECTION 3: WHAT IS HAPPENING NOW? (OPERATIONAL)                              ]
[ Active Exposure Heatmap | Top 3 Active Trades | Whale Signal Sentiment       ]
```

### Key Changes in Redesign:
- **Moved Risk to Top:** PMs care about staying in business first.
- **Compressed Trades:** Full table moved to a sub-page. Only the "Top 3" most impactful positions shown.
- **Diagnostic Focus:** "Strategy Attr" is renamed to "Why did we make/lose money?" to force focus on causality.
