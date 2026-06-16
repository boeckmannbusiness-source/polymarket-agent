# Sprint 3.1 PnL Formula Correction & Historical Discontinuity Notice

**Release Identifier:** `sprint-3.1-pnl-fix`
**Cutover Commit:** `76361f744fd2a812115ec59735660a781897cc04`
**Deployed At:** `2025-05-21 14:00:00 UTC`
**Category:** Financial Integrity
**Scope:** Shadow Validation Metrics

## Summary
During the IV&V audit for Sprint 3.1, a critical error was identified in the PnL calculation logic within `ShadowExecutionService` and `ShadowTradingService`. The error related to how position size was interpreted (treating USD investment as token quantity).

## Formula Change

### Old (Incorrect) Formula
Used in `ShadowExecutionService` and `ShadowTradingService` until Sprint 3.1:
```
PnL = (exit_price - entry_price) * size_usd
```

### New (Canonical) Formula
Effective from Sprint 3.1:
```
quantity = size_usd / entry_price
gross_pnl = (exit_price - entry_price) * quantity
```

## Impact on Historical Data
Existing shadow execution records stored in Redis or in-memory caches were calculated using the old formula.

### Cutover Boundary
- **Pre-Fix:** All records generated before `2025-05-21 14:00:00 UTC`.
- **Post-Fix:** All records generated on or after the cutover time.

### Historical Interpretation Rules
1. **Magnitude Shift:** There will be a noticeable shift in PnL magnitude for all shadow positions opened or closed after this fix.
2. **Scaling Factor:** For markets with low entry prices (e.g., $0.10), the previous formula underestimated PnL by exactly `1/entry_price` (e.g., 10x).
3. **No Backfill:** No automatic backfill has been performed to preserve the integrity of existing raw logs.
4. **Dashboard Impact:** Cumulative ROI and Total PnL charts on the dashboard will show a "kink" or sharp change in trajectory due to this scaling correction.

## Scope Clarification
- **Affected Systems:** `ShadowExecutionService`, `ShadowTradingService`, and all dependent reporting (Research Reports, Strategy Health scores, Tournament rankings).
- **Unaffected Systems:** `ShadowPortfolioService` (was already using correct logic), Live Trading PnL (uses exchange-reported fills), and Hypothesis Generation.

### KPI Interpretation Changes
1. **ROI %:** Will now correctly reflect capital utilization. Previously, ROI was distorted by the absolute price level of the entry.
2. **Win/Loss Ratio (USD):** Will show larger absolute swings in low-price markets, correctly reflecting the higher leverage/quantity inherent in those positions.
3. **Sharpe Ratio:** Validation-layer Sharpe ratios will likely change as volatility of PnL is now correctly scaled.

## Financial Validation Test Vectors
The following reference cases must be used to verify any future changes to PnL logic:

| Scenario | Entry Price | Exit Price | Size (USD) | Expected PnL (USD) | Note |
|----------|-------------|------------|------------|--------------------|------|
| Low Price Gain | 0.10 | 0.11 | 100.00 | +10.00 | 1000 shares * 0.01 |
| High Price Gain | 2.00 | 2.20 | 100.00 | +10.00 | 50 shares * 0.20 |
| Zero Guard | 0.00 | 0.50 | 100.00 | 0.00 | Prevent DivByZero |
| Negative Guard | -0.10 | 0.10 | 100.00 | 0.00 | Invalid Price |
| Standard Loss | 0.50 | 0.40 | 100.00 | -20.00 | 200 shares * -0.10 |

## Shared Implementation
All shadow modules now use the centralized `compute_shadow_pnl` helper in `app.services.shadow.pnl_utils` to ensure consistency across the system.
