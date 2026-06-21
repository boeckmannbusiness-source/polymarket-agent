# Solana Readiness Proof — Sprint 1.9C

## 1. Architecture Diff (Before → After)

| Component | Before (Binary assumptions) | After (Venue-Neutral) |
|-----------|-----------------------------|-----------------------|
| **Trade Model** | `market_id: UUID`, `outcome: NOT NULL` | `market_id: String(128)`, `outcome: NULLABLE` |
| **Fill Model** | `market_id: UUID`, `outcome: NOT NULL` | `market_id: String(128)`, `outcome: NULLABLE` |
| **Execution Intent** | Hardcoded `outcome` in instrument metadata | Intent Factory creates clean intents; outcome in `compat_outcome` |
| **Shadow Pricing** | YES/NO pricing branching in Service | Pluggable `PriceResolver` interface |
| **Persistence** | Tightly coupled to Polymarket schema | `TradeContext` and `VenueExecutionMetadata` domain models |

## 2. Persistence Lifecycle

The new lifecycle ensures that data from any venue can be persisted without modifying the core schema:

1. **Signal** (e.g., Solana Whale Signal)
2. **ExecutionIntentFactory**: Constructs `ExecutionIntent`.
   - `Instrument` symbol becomes Solana Mint.
   - `compat_outcome` is set to `None`.
3. **Planner**: Generates `TransactionPlan` (Jupiter-based).
4. **ExecutionResult**: Captured after execution.
5. **TradeContext**: Wraps the result with `VenueExecutionMetadata`.
6. **Persistence**: Saves to `Trade` table using string-based `market_id` and nullable `outcome`.

## 3. Shadow Lifecycle

The shadow layer now operates on asset resolutions rather than binary outcomes:

1. **ExecutionResult** (e.g., SOL/USDC Swap)
2. **AssetResolution**: Identifies the target asset (e.g., SOL).
3. **PriceResolver**: Resolves current price via `VenuePriceResolver`.
4. **Portfolio**: Updates `ShadowExecution` PnL using asset-agnostic `compute_shadow_pnl`.

## 4. Verification

### Solana Trade Creation (Mint-based)
- **Action**: Create trade with `market_id="So11...112"` and `outcome=None`.
- **Result**: **PASS** (Model supports string IDs and nullable outcomes).

### Polymarket Trade Creation (UUID-based)
- **Action**: Create trade with `market_id=UUID` and `outcome="YES"`.
- **Result**: **PASS** (Backward compatibility maintained via strings and nullable fields).

### Shadow Update (SOL/USDC)
- **Action**: Update shadow position for Solana mint.
- **Result**: **PASS** (PriceResolver resolves via asset resolution; no YES/NO branching).

### Shadow Update (YES/NO)
- **Action**: Update shadow position for Polymarket.
- **Result**: **PASS** (PriceResolver handles outcome-based symbols as assets).

## 5. Test Results

Run via `python -m pytest backend/app/tests/architecture/test_persistence_decoupling.py`:

```
collected 4 items

backend/app/tests/architecture/test_persistence_decoupling.py ....       [100%]

======================== 4 passed in 0.11s =========================
```

## 6. Remaining Blockers Before Sprint 2.0

**ZERO confirmed blockers remain for persistence and shadow layers.**

The system is now architecturally ready for:
- Solana SDK Integration
- Jupiter API Implementation
- Live RPC Connections
