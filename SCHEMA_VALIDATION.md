# SCHEMA_VALIDATION.md

### Persistence Verification (SQLite/PostgreSQL)
- **Test Suite**: `backend/app/tests/postgres/test_persistence.py`
- **Backend**: `sqlite+aiosqlite` (Verified locally) / `postgresql+asyncpg` (Compatible)
- **Status**: PASSED

### Models Verified
- **Trade**: Correctly persists side, size, price, and status.
- **ExchangeOrder**: Correctly persists trade link, side, size, and status.
- **Fill**: Correctly persists size, price, and fee, with links to trade and order.
- **ExecutionTrace**: Correctly persists execution metrics (price, size, side).

### Migration Status
- Verified that all required columns (including nullable `outcome` and `String(128)` `market_id`) exist and are usable for Solana-native trades.
- Row counts and constraint verification passed during integrated test run.
