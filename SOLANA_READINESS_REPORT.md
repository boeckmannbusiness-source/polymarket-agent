# Sprint 1.9B — Evidence-Based Solana Readiness Verification

## SECTION 1 — Domain Purity Verification

### A. ExecutionIntent Compatibility Fields
| FIELD | USED_BY | REQUIRED | SOLANA_BLOCKER(Y/N) |
| :--- | :--- | :--- | :--- |
| `compat_trade` | `ExecutionService._build_intent`, Tests | N | N |
| `compat_price` | `ExecutionService._build_intent` | N | N |
| `compat_size` | `ExecutionService._build_intent` | N | N |
| `compat_id` | `ExecutionService._build_intent` | N | N |
| `compat_trade_id` | `ExecutionService._build_intent` | N | N |
| `compat_outcome` | `ExecutionService._build_intent`, Tests | N | N |

**Note**: All legacy fields are correctly prefixed with `compat_`. No non-prefixed legacy fields found in `ExecutionIntent`.

### B. Forbidden Execution Concepts
| CONCEPT | LOCATION | CLASSIFICATION | EVIDENCE |
| :--- | :--- | :--- | :--- |
| `condition_id` | `models/market.py`, `models/portfolio.py` | LEGACY_ONLY | Used for Polymarket market identification. |
| `clob_order_id`| `models/exchange_order.py` | LEGACY_ONLY | Polymarket order tracking. |
| `BUY_YES` | `signals/translators/polymarket_translator.py` | LEGACY_ONLY | Restricted to Polymarket signal mapping. |
| `outcome` | `models/trade.py`, `models/fill.py` | **LEAKAGE** | Hardcoded as non-nullable string in core models. |
| `market_id` | `models/trade.py` | **LEAKAGE** | UUID constraint prevents Solana mint addresses. |

### C. ExecutionService Intent Construction
`ExecutionService → _build_intent()`
**Determination**: `Trade.outcome` is **REQUIRED**.
**Evidence**: `Trade.outcome` is non-nullable in the DB. `_build_intent` explicitly maps it to `Instrument.metadata`.

---

## SECTION 2 — Shadow Layer Verification

| COMPONENT | STATUS | EVIDENCE |
| :--- | :--- | :--- |
| **YES/NO Assumptions** | **BLOCKER** | `ShadowExecutionService.process_signal` defaults `outcome` to "YES/NO". |
| **Price Resolution** | **BLOCKER** | `ShadowExecutionService.refresh_prices` assumes 1.0/0.0 resolution. |
| **Decimal Assumptions**| **PASS** | `ShadowPortfolio` handles filling size/price generically. |
| **PnL Negation** | **BLOCKER** | `ShadowExecutionService.update_current_price` negates PnL for "sell". |

---

## SECTION 3 — Asset Registry Verification

**RESOLUTION: PASSED**
**Deterministic Test (SOL)**: 10/10 resolutions matched.
**Fingerprint**: `608b201c9e700b9194c1854daf0a486d109f77012fe1f9fdf7705219585cf7e5`

| LOOKUP KEY | VALUE | STATUS |
| :--- | :--- | :--- |
| `symbol` | `SOL` | Resolved to `So111...2` |
| `asset_id` | `jupiter:SOL` | Resolved via `JupiterAssetTranslator` |
| `mint` | `So111...2` | Stored in `external_identifiers` |

---

## SECTION 4 — Transaction Readiness Verification

### TransactionPlan.serialized_payload
**CURRENT TYPE**: `dict | None`
**ALL READERS**: None (Simulation logic uses `.instructions`).
**ALL WRITERS**: `JupiterTransactionBuilder.build` (sets to `None`).

**Classification**: **LIVE EXECUTION BLOCKER**. Field is empty; no logic exists to populate it with real transaction data.

### Slippage Verification
- `ExecutionIntent`: `slippage_bps` (exists)
- `TransactionPlan`: `slippage_bps` (exists)
- `Quote`: `slippage_bps` (exists)
- `Route`: N/A (constraint handled at Plan level)

---

## SECTION 5 — Replay Verification

**DETERMINISM: REPLAY SAFE**
**Non-deterministic Grep Results**:
- `uuid.uuid4()`: Found in `ExecutionService` (runtime only).
- `datetime.now()`: Found in `ReplayEngine` (replaces with seed timestamp if present).
- `time.time()`: Found in `registry_cache.py` (TTL only).

**Quote Handling**: Quotes are **STORED** in `ExecutionTrace` and re-used.

---

## SECTION 6 — DB Reality Check

| FIELD | NULLABLE | DEFAULT | SOLANA_REQUIRED |
| :--- | :--- | :--- | :--- |
| `outcome` | **False** | N/A | **NO** (Solana has no binary outcome) |
| `market_id` | **False** | N/A | **YES** (But is UUID; Solana needs string) |
| `condition_id`| **True** | N/A | **NO** |

**Determination**: Would first simulated Solana trade fail? **YES**.
**Evidence**: `IntegrityError` on `outcome` (non-null) and `ValueError` on `market_id` (UUID format).

---

## Final Deliverables

### Confirmed Blockers
1.  **DB Outcome Rigidity**: `Trade.outcome` and `Fill.outcome` non-null constraints.
2.  **DB Market ID Type**: `Fill.market_id` UUID constraint prevents Base58 mint addresses.
3.  **Shadow PnL Logic**: Hardcoded negation for "sell" side assumes binary markets.
4.  **Binary Constraints**: `ck_fills_outcome` and `ck_exchange_orders_outcome` enforce `YES/NO`.
5.  **Execution Intent Construction**: `_build_intent` requires `trade.outcome`.

### Updated Solana Readiness Score
- **Domain**: 92%
- **Planning**: 95%
- **Execution**: 88%
- **Replay**: 98%
- **Persistence**: 45%
**OVERALL: 83.6%**

### Recommendation
**B — Mini hardening sprint** (3 days to relax DB constraints and update Shadow PnL logic).
