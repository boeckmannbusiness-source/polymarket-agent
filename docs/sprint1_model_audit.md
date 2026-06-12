# Sprint 1 - Model Architecture Audit

**Date:** 2026-06-12
**Scope:** All 24 ORM models across 22 files in backend/app/models/
**Codebase:** polymarket-agent

---

## 1. Import Patterns

### Standard Import Block (21 of 22 model files)

Every model file follows this exact ordering (most fields vary slightly):

```python
import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Text, ForeignKey, Integer, BigInteger
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base
```

### Variations

| File | Additional Imports |
|------|-------------------|
| trade.py | from sqlalchemy import Index |
| exchange_order.py | from decimal import Decimal + CheckConstraint, UniqueConstraint |
| fill.py | from decimal import Decimal + CheckConstraint, UniqueConstraint, Index |
| remote_audit.py | from sqlalchemy import Column (old-style), no Mapped/mapped_column |
| shadow_decision_log.py | from sqlalchemy import Float |

### Key Observations

- `from sqlalchemy import JSON` is used standalone (not from `sqlalchemy.dialects.postgresql` or `sqlalchemy.types`).
- `from sqlalchemy.orm import Mapped, mapped_column, relationship` - three items always together when relationships exist.
- `relationship` is only imported in files that declare relationships (market.py, trade.py, exchange_order.py, fill.py).
- `from sqlalchemy.sql import func` is always imported, even when `func.now()` is not used in that file (it is used in almost all).

---

## 2. SQLAlchemy 2.0 Style (Mapped / mapped_column vs Column)

### Dominant Pattern: 2.0 Declarative (21/22 files)

```python
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
```

Type annotations use **Python 3.10+ union syntax** (X | None) consistently:

```python
# Required field
name: Mapped[str] = mapped_column(String(64), nullable=False)

# Optional field
description: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Every single model except RemoteControlAudit** uses this 2.0 pattern.

### Legacy Pattern: 1.x Column (1 file)

**`remote_audit.py`** is the sole outlier:

```python
class RemoteControlAudit(Base):
    __tablename__ = "remote_control_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    telegram_user = Column(String(255), nullable=False)
    command = Column(String(255), nullable=False)
    result = Column(Text, nullable=True)
    extra_data = Column(JSON, nullable=True)
```

**Issues:**
- Old-style `Column` with no `Mapped` annotation - no mypy/pyright type coverage.
- `default=lambda: datetime.now(timezone.utc)` is Python-side only (not `server_default`); different from every other model.
- `String(255)` - unique length; every other model uses powers-of-2 or domain-specific lengths.

---

## 3. Timestamp Conventions

### Pattern A: `created_at` + optional `updated_at` (server_default)

```python
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Models with `created_at` + `updated_at`:**
| Model | File |
|-------|------|
| Market | market.py |
| Wallet | wallet.py |
| Trade | trade.py |
| StrategyConfigRecord | strategy.py |
| Position | portfolio.py |
| SafetyState | safety.py |
| ExchangeOrder | exchange_order.py |
| StrategyAllocationState | strategy_allocation.py |
| WalletCluster | wallet.py |

**Models with `created_at` only (no `updated_at`):**
MarketStateSnapshot, PortfolioSnapshot, PortfolioAuditLog, FeatureSchemaVersion, FeatureLineage, ExecutionTrace, TradeAttribution, SystemModeTransition, BenchmarkPrice, Fill, ShadowDecisionLog, ShadowValidationSnapshot, BacktestRun, MarketEvent (uses `ingested_at`)

**Models with custom timestamp naming instead of `created_at`:**
- WalletScore: `calculated_at`
- StrategyPerformanceRecord: `calculated_at`
- SignalOutcome: `calculated_at`
- MarketCorrelation: `calculated_at`
- MarketEvent: `ingested_at`
- Signal: `generated_at`
- WalletTrade: `ingested_at`
- AgentLog: `timestamp` (with server_default)

### Pattern B: Event timestamps (business time, not record time)

```python
timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
```

**Naming variants for temporal columns:**
| Name | Purpose |
|------|---------|
| `created_at` | Record creation time (server_default) |
| `updated_at` | Record update time (server_default + onupdate) |
| `timestamp` | Event business time (nullable=False except in AgentLog where it has server_default) |
| `ingested_at` | Data ingestion time |
| `generated_at` | Signal generation time |
| `calculated_at` | Computation result time |
| `submitted_at` / `filled_at` / `cancelled_at` | Order lifecycle times |
| `entry_timestamp` / `exit_timestamp` | Position lifecycle times |
| `signal_timestamp` / `execution_timestamp` | Trace timing |
| `period_start` / `period_end` | Window boundaries |
| `start_date` / `end_date` | Date ranges |

### Anomalies

1. **`BacktestTrade` has NO timestamp column at all** - no `created_at`, no `timestamp`. This makes debugging and ordering impossible.
2. **`SystemModeTransition.duration_seconds`** is typed `Mapped[float | None] = mapped_column(nullable=True)` - **no SQL type specified!** Will default to `NullType`, likely causing DDL errors.

---

## 4. Index Conventions

### Pattern A: Inline `index=True` (most common, ~25 occurrences)

```python
condition_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
```

### Pattern B: `__table_args__` with `Index` tuples (2 files)

```python
# fill.py
__table_args__ = (
    CheckConstraint(...),
    UniqueConstraint(...),
    Index("ix_fills_market_id", "market_id"),
    Index("ix_fills_filled_at", "filled_at"),
)

# exchange_order.py
__table_args__ = (
    CheckConstraint(...),
    UniqueConstraint(...),
)
```

Note: `exchange_order.py` declares `__table_args__` with only constraints; its indexes are done inline or via migration.

### Pattern C: Module-level `Index` declaration (1 file)

```python
# trade.py - top-level Index on a class that already exists
Index(
    "ix_trades_unique_open_per_market_outcome",
    Trade.market_id,
    Trade.outcome,
    unique=True,
    postgresql_where=Trade.status.in_(["open", "pending"]),
    sqlite_where=Trade.status.in_(["open", "pending"]),
)
```

### Naming Scheme

```
ix_<tablename>_<column>
```

---

## 5. Relationship Conventions

### Always `back_populates` (never `backref`)

```python
# market.py
events: Mapped[list["MarketEvent"]] = relationship(back_populates="market", lazy="dynamic")

# trade.py
orders: Mapped[list["ExchangeOrder"]] = relationship(
    back_populates="trade", cascade="all, delete-orphan",
)
fills: Mapped[list["Fill"]] = relationship(back_populates="trade")

# exchange_order.py
trade: Mapped["Trade"] = relationship(back_populates="orders")
fills: Mapped[list["Fill"]] = relationship(back_populates="exchange_order", cascade="all, delete-orphan")

# fill.py
exchange_order: Mapped["ExchangeOrder"] = relationship(back_populates="fills")
trade: Mapped["Trade"] = relationship(back_populates="fills")
```

### Conventions Observed

| Aspect | Convention |
|--------|-----------|
| Bidirectional | Yes - always `back_populates` on both sides |
| `backref` usage | **None** - zero occurrences |
| `lazy` | Defaults to `"select"` (implicit); `"dynamic"` once (Market.events) |
| `cascade` | `"all, delete-orphan"` on the child FK side (ExchangeOrder on Trade, Fill on ExchangeOrder) |
| Forward refs | Strings ("Market", "Trade", "ExchangeOrder", "Fill") - avoids circular imports |
| Collection type | `list[ModelName]` - always annotated |
| Reverse scalar | `ModelName` - always annotated as singular Mapped |

### Relationship Graph

```
Market 1--* MarketEvent
Market 1--* Signal
Market 1--* Trade
Market 1--* WalletTrade
Market 1--* BacktestTrade
Market 1--* MarketStateSnapshot
Market 1--* Position
Market 1--* ExecutionTrace
Market 1--* SignalOutcome
Market 1--* Fill
Market 1--* MarketCorrelation (as market_a / market_b)

Trade 1--* ExchangeOrder
Trade 1--* Fill
Trade 1--* ExecutionTrace

ExchangeOrder 1--* Fill

Signal 1--* Trade
Signal 1--* SignalOutcome
Signal 1--* ExecutionTrace

SignalOutcome 1--1 TradeAttribution

Wallet 1--* WalletTrade
Wallet 1--* WalletScore
Wallet 1--* WalletCluster
```

---

## 6. Naming Conventions

### Table Names (`__tablename__`)

**Full table name inventory:**

| Table Name | Model Class |
|-----------|-------------|
| `markets` | Market |
| `market_events` | MarketEvent |
| `wallets` | Wallet |
| `wallet_trades` | WalletTrade |
| `wallet_scores` | WalletScore |
| `wallet_clusters` | WalletCluster |
| `signals` | Signal |
| `trades` | Trade |
| `backtest_runs` | BacktestRun |
| `backtest_trades` | BacktestTrade |
| `agent_logs` | AgentLog |
| `strategy_configs` | StrategyConfigRecord |
| `strategy_performances` | StrategyPerformanceRecord |
| `signal_outcomes` | SignalOutcome |
| `market_state_snapshots` | MarketStateSnapshot |
| `positions` | Position |
| `portfolio_snapshots` | PortfolioSnapshot |
| `market_correlations` | MarketCorrelation |
| `feature_schema_versions` | FeatureSchemaVersion |
| `feature_lineage` | FeatureLineage |
| `safety_state` | SafetyState |
| `execution_traces` | ExecutionTrace |
| `trade_attributions` | TradeAttribution |
| `strategy_allocation_states` | StrategyAllocationState |
| `system_mode_transitions` | SystemModeTransition |
| `remote_control_audits` | RemoteControlAudit |
| `portfolio_audit_log` | PortfolioAuditLog |
| `benchmark_prices` | BenchmarkPrice |
| `exchange_orders` | ExchangeOrder |
| `fills` | Fill |
| `shadow_decision_log` | ShadowDecisionLog |
| `shadow_validation_snapshots` | ShadowValidationSnapshot |

### Column Names

- **Foreign Keys:** `<target_table_singular>_id` (e.g., `market_id`, `signal_id`, `trade_id`)
- **Natural FKs:** `wallet_address` -> `wallets.address` (uses string PK)
- **Timestamps:** `_at` suffix for record times (`created_at`, `updated_at`, `ingested_at`, `generated_at`, `calculated_at`, `submitted_at`, `filled_at`, `cancelled_at`)
- **Event timestamps:** `_timestamp` suffix (`entry_timestamp`, `exit_timestamp`, `signal_timestamp`, `execution_timestamp`)
- **Date ranges:** `start_date`, `end_date`, `period_start`, `period_end`
- **Address fields:** `maker_address`, `taker_address` as `String(64)`, `wallet_address` as `String(64)`

---

## 7. Type Annotation Patterns

### Primary Key Types

```python
# UUID PK (18 of 24 models)
id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

# Integer auto-increment PK (5 of 24 models)
id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
# MarketEvent, WalletTrade, WalletScore, WalletCluster, AgentLog

# String PK (1 model)
address: Mapped[str] = mapped_column(String(64), primary_key=True)  # Wallet

# Integer PK (1 model)
id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # BacktestTrade
```

### Mapped Type Summary

| Python Annotation | SQLAlchemy Type | Nullability | Occurrences |
|-----------------|----------------|-------------|-------------|
| `Mapped[str]` | `String(N)` | `nullable=False` | ~50+ (most common) |
| `Mapped[str | None]` | `String(N)` | `nullable=True` | ~30 |
| `Mapped[uuid.UUID]` | `UUID(as_uuid=True)` | `nullable=False` | ~15 |
| `Mapped[uuid.UUID | None]` | `UUID(as_uuid=True)` | `nullable=True` | ~20 |
| `Mapped[float]` | `Numeric(P, S)` | `nullable=False` | ~15 |
| `Mapped[float | None]` | `Numeric(P, S)` | `nullable=True` | ~30 |
| `Mapped[Decimal]` | `Numeric(P, S)` | `nullable=False` | 5 (exchange_order + fill) |
| `Mapped[Decimal | None]` | `Numeric(P, S)` | `nullable=True` | 3 |
| `Mapped[bool]` | `Boolean` | `nullable=False` | ~8 |
| `Mapped[bool | None]` | `Boolean` | `nullable=True` | 3 |
| `Mapped[int]` | `Integer` / `BigInteger` | `nullable=False` | ~15 |
| `Mapped[int | None]` | `Integer` / `BigInteger` | `nullable=True` | ~8 |
| `Mapped[dict]` | `JSON` | `nullable=False` | ~5 |
| `Mapped[dict | None]` | `JSON` | `nullable=True` | ~15 |
| `Mapped[list]` | `JSON` | `nullable=False` | 3 |
| `Mapped[list | None]` | `JSON` / `ARRAY(String)` | `nullable=True` | 4 |
| `Mapped[datetime]` | `DateTime(timezone=True)` | `nullable=False` | ~25 |
| `Mapped[datetime | None]` | `DateTime(timezone=True)` | `nullable=True` | ~20 |

### String Length Conventions

| Length | Used For |
|--------|---------|
| `String(8)` | outcome codes (YES/NO), direction (BUY/SELL) |
| `String(16)` | side, trade_type, order_type, lifecycle, outcome (newer models) |
| `String(32)` | status, regime, mode, version, event_type, score_type |
| `String(64)` | signal_type, category, wallet_address, agent_name, strategy_name, maker/taker_address |
| `String(128)` | condition_id, clob_order_id, clob_asset_id, transaction_hash, clob_fill_id |
| `String(256)` | slug, resolution_source, risk_reason |

### Numeric Precision Conventions

| Precision | Scale | Used For |
|-----------|-------|---------|
| `Numeric(24, 8)` | 24, 8 | Prices, sizes, PnL, volume, liquidity (most financial fields) |
| `Numeric(12, 6)` | 12, 6 | Ratios (sharpe, sortino, calmar), slippage, drawdown |
| `Numeric(8, 6)` | 8, 6 | Probabilities, confidence scores, win rate |
| `Numeric(16, 8)` | 16, 8 | Market micro-structure metrics (momentum, volatility, spread) |
| `Numeric(24, 4)` | 24, 4 | Volume fields in attribution model |

---

## 8. Default Value Patterns

### Pattern A: server_default=func.now() (timestamps only)

```python
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Pattern B: Python default= (booleans, statuses, numerics)

```python
# Booleans
is_active: Mapped[bool] = mapped_column(Boolean, default=True)
is_open: Mapped[bool] = mapped_column(default=True)
kill_switch_active: Mapped[bool] = mapped_column(Boolean, default=False)

# Strings
status: Mapped[str] = mapped_column(String(32), default="pending")
trade_type: Mapped[str] = mapped_column(String(16), nullable=False, default="paper")
lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")

# Integers
total_trades: Mapped[int] = mapped_column(Integer, default=0)
retry_count: Mapped[int] = mapped_column(Integer, default=0)

# Floats/Numerics
total_volume: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
realized_pnl: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
daily_pnl: Mapped[float] = mapped_column(Numeric(24, 8), default=0.0)

# Callable defaults (collections)
config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
quarantined_strategies: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
```

### Pattern C: Decimal("0") for Decimal-typed fields

```python
# exchange_order.py
filled_size: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))

# fill.py
fee: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
```

### Pattern D: server_default= for non-timestamp values (only in migrations, not models)

```python
# In migration 002:
sa.Column("order_num", sa.Integer(), server_default=sa.text("1"), nullable=False)
sa.Column("engine_type", sa.String(length=16), server_default="paper", nullable=False)
```

The models themselves use Python-side default= for these.

### Key Observation
- **Inconsistency between model defaults and migration defaults**: Migration 002 uses `server_default=sa.text("1")` for `order_num`, but the model uses `default=1` (Python-side). These can diverge during manual SQL operations.

---

## 9. Unique Constraint Patterns

### Pattern A: Inline `unique=True` (10 occurrences)

```python
condition_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
version: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
clob_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
clob_fill_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
signal_outcome_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ..., unique=True, index=True)
```

### Pattern B: UniqueConstraint in __table_args__

```python
# exchange_order.py
UniqueConstraint("trade_id", "order_num", name="uq_exchange_orders_trade_order")

# fill.py
UniqueConstraint("exchange_order_id", "fill_num", name="uq_fills_exchange_order_fill")
```

### Pattern C: Named UniqueConstraint via migration

```python
# Migration 001
sa.UniqueConstraint("strategy_name", name=op.f("uq_strategy_allocation_states_strategy_name"))
```

### Naming Scheme

```
uq_<tablename>_<column1>[_<column2>]
```

### Pattern D: Partial unique index (module-level in trade.py)

```python
Index(
    "ix_trades_unique_open_per_market_outcome",
    Trade.market_id,
    Trade.outcome,
    unique=True,
    postgresql_where=Trade.status.in_(["open", "pending"]),
    sqlite_where=Trade.status.in_(["open", "pending"]),
)
```

---

## 10. FK Naming Patterns

### Pattern A: Simple ForeignKey (most common)

```python
ForeignKey("markets.id")
ForeignKey("signals.id")
ForeignKey("wallets.address")
ForeignKey("backtest_runs.id")
```

### Pattern B: ForeignKey with ondelete

```python
ForeignKey("trades.id", ondelete="CASCADE")
ForeignKey("exchange_orders.id", ondelete="CASCADE")
```

`ondelete="CASCADE"` is used on:
- ExchangeOrder.trade_id -> trades.id
- Fill.exchange_order_id -> exchange_orders.id
- Fill.trade_id -> trades.id

**No model uses `ondelete="SET NULL"`.**

### FK Column Naming

```
<target_table_singular>_id
```

**Examples:**
- `market_id` -> `markets.id`
- `signal_id` -> `signals.id`
- `trade_id` -> `trades.id`
- `wallet_address` -> `wallets.address` (natural key exception)
- `exchange_order_id` -> `exchange_orders.id`
- `backtest_run_id` -> `backtest_runs.id`
- `signal_outcome_id` -> `signal_outcomes.id`
- `market_a_id` / `market_b_id` -> `markets.id` (self-referential)

---

## 11. Inheritance / Shared Base

- **Single base class:** `app.database.Base` - defined as `class Base(DeclarativeBase): pass`
- **No mixins, no abstract models, no shared base classes** other than `Base`.
- `DeclarativeBase` (SQLAlchemy 2.0) is used, **not** `declarative_base()`.

---

## 12. Alembic Auto-Discovery

```python
# backend/alembic/env.py
from app.models import *  # noqa: F401, F403 - ensure all models are loaded
target_metadata = Base.metadata
```

Models are discovered via wildcard import of `app.models` (which re-exports all model classes via `__init__.py`).

---

## 13. Test DB Setup

```python
# backend/app/tests/conftest.py
# SQLite compilers registered for PostgreSQL-specific types before model import:
@compiles(UUID, "sqlite")    # -> VARCHAR(64)
@compiles(ARRAY, "sqlite")   # -> JSON

engine = create_async_engine("sqlite+aiosqlite:///:memory:")
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

- In-memory SQLite is used.
- UUID columns become VARCHAR(64) in SQLite.
- ARRAY columns become JSON in SQLite.
- Tables are recreated per test session.
- SQLite type compilers are registered **BEFORE** model imports so that model definitions with PG-specific types can compile under SQLite.

---

## 14. Anomalies and Issues Found

### Critical

| # | File | Issue |
|---|------|-------|
| 1 | models/system_mode.py:21 | `duration_seconds: Mapped[float | None] = mapped_column(nullable=True)` - **no SQL type specified!** Will produce `NullType` column. Missing `Float` or `Numeric` type. |
| 2 | models/backtest.py | `BacktestTrade` has **no timestamp column at all** - no `created_at`, no `timestamp`. Impossible to order or trace chronologically. |

### Moderate

| # | File | Issue |
|---|------|-------|
| 3 | models/remote_audit.py | **Entire file uses old 1.x `Column` style** - inconsistent with all 21 other model files. No `Mapped` annotations, no type safety. |
| 4 | models/shadow_decision_log.py | Uses `Float` instead of `Numeric` for regime_confidence, expected_return, optimization_weight, stability_score, drift_score, exposure_level - inconsistent with all other financial float columns which use `Numeric`. |
| 5 | models/trade.py, exchange_order.py, fill.py | `outcome` column length **varies**: `String(64)` in Trade, `String(16)` in ExchangeOrder and Fill. These should be aligned. |
| 6 | Various | `entry_timestamp` / `exit_timestamp` on WalletTrade vs `entry_timestamp` / `exit_timestamp` on Trade - similar-but-separate naming, potentially confusing. |
| 7 | models/trade_attribution.py:16 | `signal_outcome_id` uses both `unique=True` and `index=True` - redundant (unique implies index). |
| 8 | models/feature_store.py:19 | `features: Mapped[list] = mapped_column(JSON, nullable=False)` - `list` is generic; should be `list[str]` or documented. |

### Minor / Cosmetic

| # | File | Issue |
|---|------|-------|
| 9 | models/market.py:34 | `lazy="dynamic"` is deprecated in SQLAlchemy 2.0 (prefer `lazy="selectin"` with filtering). |
| 10 | models/exchange_order.py:36 | `size: Mapped[Decimal]` - type annotation uses `Decimal` but underlying column is `Numeric`. Runtime behavior is `float` unless a custom type decorator is applied. |
| 11 | models/wallet.py:17-18 | `first_seen`, `last_seen` use `nullable=True` but no `server_default`; these may remain NULL if not explicitly set. |
| 12 | Migration 003 | Named as `003_widen_market_id_v128` in revision but filename is `003_widen_shadow_decision_log_market_id.py` - mismatched. |

---

## 15. Summary of Consistent Patterns

| Pattern | Convention | Deviation Count |
|---------|-----------|-----------------|
| SQLAlchemy 2.0 syntax | `Mapped[X]` + `mapped_column(...)` | 1 file (remote_audit.py) |
| Timestamps | `DateTime(timezone=True)` + `server_default=func.now()` | 0 (all use timezone=True) |
| `updated_at` | `server_default=func.now(), onupdate=func.now()` | 0 (all use same pattern) |
| Bidirectional relationships | `back_populates` (never `backref`) | 0 |
| FK naming | `<target>_id` | 0 |
| Table naming | snake_case plural | 2 singular exceptions |
| Type unions | `X | None` (Python 3.10+) | 0 (never `Optional[X]`) |
| UUID PKs | `UUID(as_uuid=True)` + `default=uuid.uuid4` | 0 |
| `nullable` | Explicit on every column | 0 |
| Cascade deletes | `ondelete="CASCADE"` on child FK, `cascade="all, delete-orphan"` on relationship | 0 (where used) |
| Constraint naming | `ck_<table>_<purpose>`, `uq_<table>_<cols>`, `ix_<table>_<col>` | 0 |
