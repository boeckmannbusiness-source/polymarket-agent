# Sprint 3.1 PnL Formula Correction & Historical Discontinuity Notice

**Date:** 2025-05-21
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
- **Discontinuity:** There will be a noticeable shift in PnL magnitude for all shadow positions opened or closed after this fix.
- **Scaling:** For markets with low entry prices (e.g., $0.10), the previous formula underestimated PnL by 10x.
- **Migration:** No automatic backfill has been performed to preserve the integrity of existing logs. Users should rely on metrics generated after 2025-05-21 for accurate strategy evaluation.

## Shared Implementation
All shadow modules now use the centralized `compute_shadow_pnl` helper in `app.services.shadow.pnl_utils` to ensure consistency across the system.
