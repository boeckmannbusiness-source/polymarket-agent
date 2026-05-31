# Production Dashboard Specification: Polymarket Intelligence Agent

This document defines the exact specification for the production-grade dashboard, optimized for a Portfolio Manager (PM) overseeing a fully autonomous quantitative trading system.

## 1. Design Philosophy: The PM's 30-Second Rule
The dashboard is designed for "Negative Selection"—identifying reasons to intervene or halt the system. It must answer these questions within seconds:
1. **Shock Test:** Is the equity trend broken? (PnL & 7D Curve)
2. **Safety Check:** Is the system within risk bounds and healthy? (Drawdown, Utilization, Health)
3. **Diagnostic Logic:** Why did we make/lose money? (Attribution & Alpha vs. Beta)

---

## 2. Layout Architecture (PM-First Workflow)

### A. Critical Header (The "Pulse")
- **Purpose:** Immediate visual confirmation of status.
- **Widgets:**
  - **Daily PnL:** Absolute USD + % change.
  - **Equity Sparkline (7D):** Area chart showing trend.
  - **Current Drawdown:** % off high-water mark (Critical risk metric).
  - **System Health LED:** Single status indicator (Green/Yellow/Red).

### B. Risk & Safety Section (The "Guardrails")
- **Purpose:** Monitor capital deployment and model integrity.
- **Widgets:**
  - **Capital Utilization:** Circular gauge showing % of bankroll deployed vs. max limit.
  - **Exposure Heatmap:** Visual concentration of risk by market sector.
  - **Kill Switch:** High-visibility "Halt All" control.

### C. Diagnostic Attribution (The "Why")
- **Purpose:** Explain performance causality.
- **Widgets:**
  - **Alpha vs. Beta Overlay:** Equity curve vs. Market benchmark.
  - **Strategy PnL Rankings:** Bar chart of performance by signal type (Whale, Momentum, etc.).
  - **Slippage & Fees Impact:** USD value lost to execution friction.

### D. Operational Feed (The "Now")
- **Purpose:** Minimalist view of current activity.
- **Widgets:**
  - **Top 3 Active Positions:** Most impactful trades by size/PnL.
  - **Whale Signal Sentiment:** Current bias of high-win-rate wallets.
  - **Decision Narrative:** One-sentence summary of the system's current focus.

---

## 3. Widget Ranking & Data Sources

| Rank | Widget | Visual Type | Data Source |
| :--- | :--- | :--- | :--- |
| **Critical** | Equity Curve | Area Chart | `/api/v1/portfolio/history` |
| **Critical** | Utilization | Gauge | `/api/v1/risk/status` |
| **Critical** | Drawdown | Large Stat | `/api/v1/risk/status` |
| **Critical** | System Health | LED / Dot | `/api/v1/health` |
| **Important**| Strategy Attr. | Bar Chart | `/api/v1/analytics/strategies` |
| **Important**| Alpha vs Beta | Dual Line | `/api/v1/analytics/attribution`|
| **Important**| Slippage | Stat/Bar | `/api/v1/trades/slippage` |
| **Nice to Have**| Active Trades | Mini-Table | `/api/v1/trades/active` |

---

## 4. Visual Identity & Mobile
- **Theme:** "Hedge-Fund Dark"—Black backgrounds (#000000), Slate borders, High-contrast data points.
- **Mobile Layout:** Vertical scroll prioritizing the "Critical Header" and "Risk & Safety" sections. No complex tables; cards only.
- **Typography:** Monospace for all financial figures (Inter for labels).
- **Colors:**
  - **Profit:** Emerald 500
  - **Loss/Risk:** Rose 500
  - **System Watch:** Amber 400
  - **Deployment:** Indigo 500
