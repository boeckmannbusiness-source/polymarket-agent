# Trading Dashboard Audit

This document provides a comprehensive audit of the current trading dashboard, evaluating its usability, density, and effectiveness for system operators.

## 1. Current State Assessment

### Summary
The system currently has a functional set of dashboards divided into a high-level overview (`/`), a stability-focused cockpit (`/cockpit`), and data-specific views (`/trades`, `/signals`, `/whales`, `/markets`).

### Evaluation Metrics
| Metric | Rating | Notes |
| :--- | :--- | :--- |
| **Operator Usability** | High | Clear navigation and modular components. |
| **Information Density** | Low-Medium | Main dashboard is sparse; Cockpit is well-balanced; Tables are standard. |
| **Cognitive Load** | Medium | The separation of concerns helps, but raw tables increase load for performance analysis. |
| **Mobile Usability** | Moderate | Layouts are responsive but tables suffer on small screens. |
| **Decision-making Speed** | Moderate | Cockpit is fast for stability; Trade/Signal evaluation is slower. |

### Component Review

| Component | Page | Status | Recommendation |
| :--- | :--- | :--- | :--- |
| **StatCard (4-grid)** | Main | **Simplify** | Merge into a compact global header bar. |
| **Top Markets** | Main | **Remove** | Redundant with Markets page; move detailed view there. |
| **Top Wallets** | Main | **Remove** | Redundant with Whales page. |
| **Recent Signals** | Main | **Keep** | High utility for quick glance. |
| **Active Trades** | Main | **Keep** | High utility for quick glance. |
| **SystemHealthHeader** | Cockpit | **Keep** | Single source of truth. Essential. |
| **PrimarySignal** | Cockpit | **Merge** | Integrate into Health Header or Decision Banner to reduce duplication. |
| **SystemNarrative** | Cockpit | **Keep** | Excellent for low-cognitive-load status updates. |
| **DecisionBanner** | Cockpit | **Keep** | Critical for operational guidance. |
| **StabilityMetrics** | Cockpit | **Simplify** | Reduce visual noise; focus on outliers. |
| **ModeTimeline** | Cockpit | **Keep** | Essential for post-mortem/incident review. |

---

## 2. Redundant Components
- **Main Dashboard Lists:** "Top Markets" and "Top Wallets" provide little value for active trading oversight.
- **Cockpit PrimarySignal:** Overlaps significantly with the Health Header. Both show the current state (Stable/Watch/Unstable) and primary drivers.

## 3. Missing Components
- **Portfolio Equity Curve:** No visual representation of capital over time.
- **Risk Exposure View:** No clear view of current exposure by market or strategy.
- **Alpha Attribution:** Hard to tell which signals or strategies are performing best.
- **Capital Growth Visualization:** Distinction between paper and live trading growth.
- **Strategy Performance:** Performance metrics per-agent or per-strategy.

---

## 4. Proposed Dashboard Architecture

### A) Daily Monitoring (The "Morning View")
*Goal: Understand overnight performance and current health in 5 seconds.*
1. **Global Header (Sticky):**
   - [PnL: +$1,200 (+2.1%)] | [Equity: $11,200] | [Mode: AUTONOMOUS] | [Health: STABLE]
2. **Portfolio Equity Curve:** 7-day sparkline or area chart showing capital growth vs. benchmark (e.g., BTC or Market Avg).
3. **Alpha Attribution Map:** Grid of colored tiles representing strategy performance (Whale tracking, Momentum, etc.). Green = Profitable, Red = Loss-making.
4. **Active Exposure Gauge:** Circular gauge showing % of capital deployed vs. max limit (e.g., 45% used of 80% limit).

### B) Active Trading Oversight (The "Operational View")
*Goal: Monitor live execution and evaluate new signals.*
1. **Live Signal Stream (Ranked):**
   - High-confidence signals at top with "Strength" bar and "Why" popover.
2. **Open Trades Board:**
   - Visual progress bars for Stop-Loss (Red) and Take-Profit (Green) proximity.
   - Live PnL per position updating in real-time.
3. **Whale Intelligence Feed:**
   - Activity log filtered for wallets with >70% win-rate or those currently active in markets where the system has open positions.
4. **Risk Exposure Sunburst/Treemap:**
   - Visual breakdown of exposure by market sector or volatility tier.

### C) Emergency Incident Response (The "War Room View")
*Goal: Immediate diagnosis and intervention.*
1. **System Anomaly Banner:** Flashy (but not distracting) top-level alert if `instability_score > 0.7`.
2. **Tactical Kill-Switch Grid:**
   - [HALT ALL] | [CLOSE ALL POSITIONS] | [PAUSE RESEARCH] | [ENTER WATCH MODE]
3. **System Forces (High-Res):**
   - Real-time line charts for Pressure (Backlog), Stability (Mode flips), and Throughput (TPS).
4. **Decision Narrative (Auto-Scrolling):**
   - "2s ago: Rejected Momentum signal due to low liquidity."
   - "5s ago: Adjusted SL for Market X to +2%."

---

## 5. Wireframe Layout Descriptions

### 1. Unified Cockpit (Consolidated Monitoring)
```text
[ Health Header: MODE | STABILITY | RISK | 24h PnL ]
--------------------------------------------------
[ Decision Banner: ACTION RECOMMENDATION         ]
--------------------------------------------------
[ Narrative: "System stable, following whale..." ]
--------------------------------------------------
[ (Main Left)            | (Side Right)          ]
[ Equity Curve Chart     | Active Exposure Gauge ]
[                        | Risk Utilization      ]
--------------------------------------------------
[ (Bottom Left)          | (Bottom Right)        ]
[ Recent High-Conf Signals| Active Trades (PnL)  ]
```

### 2. Alpha & Strategy View
```text
[ Strategy Selector: ALL | WHALE | MOMENTUM | ... ]
--------------------------------------------------
[ Performance Matrix: Win Rate | Profit Factor | DD]
--------------------------------------------------
[ Alpha Attribution (Bar Chart):                  ]
[ Strategy A: [##########] +$500                  ]
[ Strategy B: [####]       +$120                  ]
[ Strategy C: [##]         -$50                   ]
--------------------------------------------------
[ Signal Backtest vs Reality (Line Chart)         ]
```

### 3. Risk & Wallet Intelligence
```text
[ Risk Limit Status: Exposure 45% | DD 2.1%       ]
--------------------------------------------------
[ (Left)                 | (Right)               ]
[ Exposure by Market     | Top Wallet Correlation]
[ [Sector A: 30%]        | [Wallet X: 80% Match] ]
[ [Sector B: 15%]        | [Wallet Y: 65% Match] ]
--------------------------------------------------
[ Critical Whale Watch: List of relevant active   ]
[ wallets and their current bias (Bullish/Bearish)]
```
