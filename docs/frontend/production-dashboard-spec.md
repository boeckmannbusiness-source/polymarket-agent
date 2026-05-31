# Production Dashboard Specification: Polymarket Intelligence Agent

This document defines the exact specification for the production-grade dashboard, designed for high-stakes operational oversight with a hedge-fund style user experience.

## 1. Design Philosophy: The 3-Second Rule
The dashboard's primary objective is to answer five critical questions within 3 seconds of page load:
1. **Am I making money?** (PnL & Equity Curve)
2. **How much capital is deployed?** (Exposure Gauge)
3. **What is my current risk?** (Drawdown & VaR)
4. **Which strategies are performing?** (Alpha Attribution)
5. **Is the system healthy?** (System Status)

---

## 2. Layout Architecture

### A. Hero Section (Executive Overview)
- **Purpose:** Immediate situational awareness of total portfolio value and performance.
- **Data Source:** Backend `portfolio_service` (Aggregated balance + realized/unrealized PnL).
- **Visual Component:** Large, high-contrast typography with "Statement of Account" feel.
- **Desktop Layout:** Top full-width banner.
- **Mobile Layout:** Stacked cards at top.
- **Widgets:**
  - **Net Liquidation Value:** Current total equity in USD.
  - **Daily PnL:** Absolute and percentage change since 00:00 UTC (Dynamic color: Green/Red).
  - **Total Return:** Cumulative PnL since inception.

### B. Portfolio Equity Curve (Visual Centerpiece)
- **Purpose:** Primary visual indicator of performance trends and capital growth.
- **Data Source:** Time-series database (InfluxDB/Prometheus) or Redis timeseries of `total_equity`.
- **Visual Component:** Large Area Chart (Gradient fill). Interactive tooltips for historical points.
- **Desktop Layout:** Central large column (66% width).
- **Mobile Layout:** Full-width chart below Hero.
- **Widgets:**
  - **Master Equity Chart:** 1D, 7D, 30D, ALL toggles. Compare against BTC/ETH benchmarks.

### C. Portfolio Metrics Section
- **Purpose:** Quantitative risk and deployment metrics.
- **Data Source:** `RiskService` and `TradeService`.
- **Visual Component:** Compact metric grid with sparklines.
- **Desktop Layout:** Right sidebar (33% width) adjacent to Equity Curve.
- **Mobile Layout:** 2x2 grid below Equity Curve.
- **Widgets:**
  - **Capital Utilization:** Circular gauge (% of total bankroll currently in positions).
  - **Current Drawdown:** Percentage off the high-water mark.
  - **Max VaR (Value at Risk):** Estimated potential loss at 95% confidence.

### D. Strategy Attribution Section
- **Purpose:** Identify which alpha signals are driving returns.
- **Data Source:** `TradeService` grouped by `strategy_id` or `signal_type`.
- **Visual Component:** Horizontal Bar Chart or Treemap.
- **Desktop Layout:** Mid-section full-width or split with Active Positions.
- **Mobile Layout:** Vertical list with performance bars.
- **Widgets:**
  - **PnL by Strategy:** Rankings (Whale Following, Momentum, Event Arbitrage).
  - **Win Rate Matrix:** Strategy-specific hit rates.

### E. Active Positions Section
- **Purpose:** Real-time monitoring of live market exposure.
- **Data Source:** `TradeService.get_active_trades()`.
- **Visual Component:** Clean, high-density table with "Trade Tickets" look.
- **Desktop Layout:** Lower-mid section.
- **Mobile Layout:** Swipeable cards.
- **Widgets:**
  - **Active Trade Table:** Market, Side, Size, Entry, Current Price, Unr. PnL, SL/TP Proximity (visual bar).

### F. System Health Section
- **Purpose:** Verification of autonomous agent operational integrity.
- **Data Source:** `MonitoringService` / Heartbeats.
- **Visual Component:** Minimalist status dots (Status LED style).
- **Desktop Layout:** Bottom footer or top-right "Control Center" icon.
- **Mobile Layout:** Bottom persistent bar.
- **Widgets:**
  - **Layer Health:** Data Ingestion, LLM Analysis, Execution Engine, Risk Guard.
  - **Latency Monitor:** End-to-end signal-to-execution lag.

---

## 3. Widget Specification Detail

| Widget | Type | Desktop | Mobile | Data Source |
| :--- | :--- | :--- | :--- | :--- |
| **Net Liquidity** | Big Stat | Header Left | Top Full | `/api/v1/portfolio/summary` |
| **Equity Curve** | Area Chart | Center (Large) | Full Width | `/api/v1/portfolio/history` |
| **Strategy PnL** | Bar Chart | Mid Left | List | `/api/v1/analytics/strategies` |
| **Risk Gauge** | Radial | Mid Right | 1/2 Width | `/api/v1/risk/status` |
| **Trade Table** | Data Grid | Bottom | Full Width | `/api/v1/trades/active` |
| **Agent Health** | LED Grid | Bottom Right | Bottom Bar | `/api/v1/health` |

---

## 4. Visual Identity
- **Theme:** Ultra-dark mode (Black backgrounds, slate/gray borders).
- **Typography:** Inter or SF Pro (System fonts) for legibility. Monospace for all financial figures.
- **Color Palette:**
  - **Success:** Emerald 500 (#10b981)
  - **Warning:** Amber 400 (#fbbf24)
  - **Danger:** Rose 500 (#f43f5e)
  - **Primary:** Indigo 500 (#6366f1)
