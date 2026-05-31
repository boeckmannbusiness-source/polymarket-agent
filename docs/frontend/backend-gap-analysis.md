# Gap Analysis: Dashboard Specification vs. Backend Implementation

This document identifies the technical gaps between the PM-centric dashboard specification and the current backend capabilities.

## 1. Widget Data Source & Readiness Audit

| Widget | Backend Source | Status | Complexity | Schema Changes |
| :--- | :--- | :--- | :--- | :--- |
| **Daily PnL** | `PortfolioSnapshot` | **READY** | LOW | None |
| **Equity Curve (7D)**| `PortfolioSnapshot` | **PARTIAL**| MEDIUM | Need 1h interval snapshots |
| **Current Drawdown** | `PortfolioSnapshot` | **READY** | LOW | None |
| **System Health** | `/health` / Agent Logs | **PARTIAL**| LOW | Standardize agent heartbeats |
| **Utilization %** | `PortfolioSnapshot` | **READY** | LOW | None |
| **Exposure Heatmap** | `MarketCorrelation` | **PARTIAL**| MEDIUM | Sector tags in `Market` model |
| **Alpha vs. Beta** | New Analytics | **MISSING** | HIGH | Add benchmark price tracking |
| **Strategy PnL** | `TradeAttribution` | **READY** | LOW | None |
| **Slippage Impact** | `Trade.slippage` | **READY** | LOW | None |

---

## 2. Historical Equity Replay Analysis

**Can the current backend reconstruct historical portfolio equity?**
*No.* While `PortfolioSnapshot` exists, there is no high-frequency (e.g., 5m or 1h) automated snapshotting mechanism, nor is there a pure event-sourced model for retroactive reconstruction without "dirty" state.

### Missing Events for Full Replay:
1. **Cash Transfer Events:** Deposits/Withdrawals from the bankroll.
2. **Mark-to-Market (MtM) Snapshots:** Periodic recording of unrealized PnL for all open positions.
3. **Fee Accrual Events:** Non-trade related costs (e.g., rebalancing fees).

### Proposed Storage Model & Schema:

**New Table: `portfolio_audit_log`**
Used for event-sourced reconstruction.
```python
class PortfolioAuditLog(Base):
    __tablename__ = "portfolio_audit_log"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str]  # TRADE_OPEN, TRADE_CLOSE, MTM_UPDATE, CASH_FLOW
    delta_cash: Mapped[float]
    delta_exposure: Mapped[float]
    reference_id: Mapped[uuid.UUID] # Link to Trade or MarketSnapshot
    timestamp: Mapped[datetime]
```

**Proposed Storage Strategy:**
- **Primary:** PostgreSQL for audit logs and hourly snapshots.
- **Cache/Fast Replay:** Redis Timeseries for 5m interval "hot" equity data (Last 30 days).

### Estimation:
- **Implementation Complexity:** MEDIUM (Requires a background task for MtM updates).
- **Retention Cost:** LOW. Assuming 1 snapshot/hour + 1 audit log/event, storage will grow by ~100MB/year.

---

## 3. Gap Analysis Summary

### Critical Missing Components:
1. **Benchmark Integration:** The `Alpha vs. Beta` widget requires a new service to fetch and store benchmark prices (e.g., BTC or Market Index).
2. **High-Frequency Snapshots:** The `Equity Curve` requires an automated task (e.g., Celery/APScheduler) to trigger `PortfolioSnapshot` every hour.
3. **Sector Tagging:** To enable the `Exposure Heatmap`, the `Market` model needs a `category` or `sector` field.

### Next Steps:
1. Implement the `PortfolioAuditLog` model.
2. Create an `AnalyticsService` to compute Alpha vs. Beta metrics.
3. Add a background task for hourly Mark-to-Market portfolio recording.
