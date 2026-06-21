# Evidence Matrix — Sprint 1.9D Solana Authorization

| CLAIM | CODE LOCATION | TEST | RESULT |
|-------|---------------|------|--------|
| **trades.outcome nullable** | `backend/alembic/versions/007_...py`, `backend/app/models/trade.py` | `backend/app/tests/integration/test_persistence_schema.py` | PASS |
| **trades.market_id string-compatible** | `backend/app/models/trade.py` (String(128)) | `backend/app/tests/integration/test_persistence_schema.py` | PASS |
| **fills.outcome nullable** | `backend/alembic/versions/007_...py`, `backend/app/models/fill.py` | `backend/app/tests/integration/test_persistence_schema.py` | PASS |
| **fills.market_id string-compatible** | `backend/app/models/fill.py` (String(128)) | `backend/app/tests/integration/test_persistence_schema.py` | PASS |
| **Venue-based PriceResolver selection** | `backend/app/services/shadow/pricing/registry.py` | `backend/app/tests/architecture/test_price_resolution_decoupling.py` | PASS |
| **No binary outcome branching in PriceResolver** | `backend/app/services/shadow/shadow_execution_service.py` | `backend/app/tests/architecture/test_price_resolution_decoupling.py` | PASS |
| **SOL Mint Resolution (So111...112)** | `backend/app/services/assets/translators/jupiter_asset_translator.py` | `backend/app/tests/integration/test_asset_registry_mints.py` | PASS |
| **Deterministic Asset Fingerprint** | `backend/app/services/assets/asset_resolution_fingerprint.py` | `backend/app/tests/integration/test_asset_registry_mints.py` | PASS (10/10) |
| **base64 Transaction Payload contract** | `backend/app/domain/planning/transaction_plan.py` | `backend/app/tests/architecture/test_transaction_payload_contract.py` | PASS |
| **Slippage propagation in Planner** | `backend/app/services/planning/planner.py` | `backend/app/tests/architecture/test_slippage_contract.py` | PASS |

## Migration Proof
- **SQL Diff:** `backend/MIGRATION_PROOF.sql` generated via `alembic upgrade --sql`.
- **Validation:** Integration test confirms nullable outcome and long market_id support in PostgreSQL-compatible schema.

## Runtime Call Graph
```
ExecutionService
  → ShadowExecutionService.refresh_prices()
    → PriceResolverRegistry.get(venue)
      → PriceResolver (VenuePriceResolver)
        → AssetResolution (Venue-Agnostic)
```

## Determinism Output
- **10 Identical resolutions for SOL mint:** 100% Identity.
- **Fingerprint:** `c0f69024056d15e22960f24588a3b917e6eef3cc339a5137e86a951a7d3b1f71`
- **Reference Document:** `DETERMINISM_PROOF.md`

## Remaining REAL blockers before Sprint 2.0
- **None identified.** All readiness claims for Solana/Jupiter integration have been evidenced.

## Final Authorization Status
**AUTHORIZED FOR SPRINT 2.0**
