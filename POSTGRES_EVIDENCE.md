# PostgreSQL Evidence

## Objective
Verify schema integrity and persistence of execution models.

## Models Verified
- `TransactionEnvelope`
- `SimulationReceipt`
- `ExecutionTrace`
- `AuthorizationSnapshot`

## Integrity Results
- JSONB storage for complex nested models (SimulationSnapshot) confirmed.
- Decimal precision (24, 8) maintained for all financial fields, verified via `TradeValidation` model test.
- Migration paths for Solana-specific fields (nullable outcomes, mint addresses) verified.
