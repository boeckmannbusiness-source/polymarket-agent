# Dashboard Implementation Plan: PM Operational Oversight

This plan outlines the staged rollout of the production-grade PM dashboard, focusing on maximizing ROI with minimum engineering effort.

---

## Phase 1: High-ROI Quick Wins (The "Pulse" Dashboard)
*Goal: Deploy the critical PM widgets using existing backend data.*

### 1. Daily PnL & Equity Curve
- **Backend Changes:**
  - Expose `GET /api/v1/portfolio/history` to return a time-series of `PortfolioSnapshot` records.
- **Frontend Changes:**
  - Create `PortfolioHero` component with large PnL display.
  - Implement `MasterEquityChart` using `recharts` to plot the snapshot history.
- **Database Changes:** None.
- **Effort:** LOW (2-3 days).

### 2. Risk & Deployment (Drawdown & Utilization)
- **Backend Changes:**
  - Ensure `GET /api/v1/portfolio/summary` returns updated `drawdown` and `total_exposure`.
- **Frontend Changes:**
  - Implement `RadialUtilizationGauge`.
  - Implement `DrawdownStatus` card.
- **Database Changes:** None.
- **Effort:** LOW (1 day).

### 3. Attribution (Strategy & Slippage)
- **Backend Changes:**
  - Use `GET /api/v1/analytics/strategy-summary` for strategy rankings.
  - Expose `GET /api/v1/analytics/slippage-summary` to aggregate `Trade.slippage`.
- **Frontend Changes:**
  - Implement `StrategyPerformanceBarChart`.
  - Implement `SlippageImpactMetric`.
- **Database Changes:** None.
- **Effort:** MEDIUM (3-4 days).

### 4. System Health Indicator
- **Backend Changes:** Standardize `/api/v1/health` response to include agent heartbeat status.
- **Frontend Changes:** Add `SystemStatusLED` to the global header.
- **Database Changes:** None.
- **Effort:** LOW (1 day).

---

## Phase 2: Design - Exposure & Categorization (Not for implementation)
*Goal: Plan for multi-market risk visualization.*

- **Requirement:** Group exposure by market sector (e.g., Politics, Crypto, Sports).
- **Backend:**
  - Add `category` field to `Market` model.
  - Update `PortfolioSnapshot` to aggregate exposure by `category`.
- **Frontend:** Implement `ExposureSunburst` or `ExposureTreemap`.

---

## Phase 3: Technical Design - Historical Reconstruction
*Goal: Perfect data integrity for auditing and backtesting.*

### 1. PortfolioAuditLog
- **Concept:** Every balance change (trade, fee, transfer) must be recorded as an immutable event.
- **Schema:**
  - `id`, `event_type` (TRADE, FUNDING, FEE), `amount`, `reference_id`, `timestamp`.
- **Storage:** PostgreSQL (Long-term audit trail).

### 2. Historical Equity Reconstruction
- **Mechanism:** To calculate equity at time *T*, sum all `PortfolioAuditLog` events up to *T* and add to initial balance.
- **Performance:** Use daily "Checkpoints" (consolidated snapshots) to avoid replaying thousands of events for every query.

### 3. Alpha vs. Beta Attribution
- **Mechanism:**
  - Track a benchmark index (e.g., Polymarket Volume Weighted Index).
  - Calculate `Portfolio_Return - Benchmark_Return` to isolate strategy alpha.
  - Requires a new `BenchmarkPrice` table and a background fetcher.

---

## Summary of Effort (Phase 1)
| Widget | Backend | Frontend | Effort |
| :--- | :--- | :--- | :--- |
| **Daily PnL / Equity**| MEDIUM | MEDIUM | **MEDIUM** |
| **Risk Metrics** | LOW | LOW | **LOW** |
| **Attribution** | MEDIUM | MEDIUM | **MEDIUM** |
| **Health** | LOW | LOW | **LOW** |

**Total Estimated Phase 1 Duration:** 8-10 days for a production-ready MVP.
