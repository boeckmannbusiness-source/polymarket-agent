# IV&V Audit Evidence Report - Polymarket Intelligence Agent

## A1 Financial PnL Audit (CRITICAL)

| File | Formula | Correct? | Verdict |
|------|---------|----------|---------|
| `shadow_portfolio_service.py` | `(exit - entry) * (size / entry)` | YES | **REFERENCE** |
| `shadow_execution_service.py` | `(exit - entry) * size` | NO | **TRUE BUG** |
| `shadow_trading_service.py` | `(exit - entry) * size` | NO | **TRUE BUG** |

**Evidence:**
- `shadow_execution_service.py:147`: `execution.realized_pnl = (exit_price - execution.entry_price) * execution.size`
- `shadow_trading_service.py:94`: `pos.pnl = (exit_price - pos.entry_price) * pos.size`
- `shadow_portfolio_service.py:20`: `quantity = size_usd / entry_price; gross = (exit_price - entry_price) * quantity`

**Impact:** **BLOCKER**. All PnL metrics used for research, tournaments, and analytics are mathematically incorrect by a factor of `1/entry_price`.

---

## A2 Shadow Isolation Audit (HIGH)

**Dependency Graph:**
ShadowExecutionService → StrategyHealthService → ResearchReportService → API
ShadowExecutionService → ShadowPromotionService → ShadowAutoPromotionService → API

**Verdict:** **INTENTIONAL LIFECYCLE INPUT**.
While "shadow" data is used to make promotion decisions, this appears to be the intended design of the "Tournament" and "Lifecycle" modules. No leakage into live execution scoring or hypothesis generation was found.

---

## A3 Concurrency Audit (HIGH)

**Verdict:** **REPRODUCED**.
`ShadowExecutionService` maintains an in-memory `_executions` dict that is loaded once at startup. Every update calls `_save_to_redis` which overwrites the entire object in a Redis hash.
- **Path:** `update_current_price` -> updates `self._executions[id]` -> `_save_to_redis`.
- **Risk:** Multi-worker deployments will suffer from lost updates if workers have different in-memory states.
- **Blast Radius:** High (All shadow metrics).

---

## A4 Background Loop Reliability (MEDIUM)

| File | Line | Severity | Verdict |
|------|------|----------|---------|
| `main.py` | 508 | **HIGH** | **UNSAFE**. Swallows stream pressure monitor failures. |
| `main.py` | 706 | **HIGH** | **UNSAFE**. Swallows DB pool monitor failures. |
| `main.py` | 150 | **MEDIUM** | **UNSAFE**. Swallows Redis setup errors. |

---

## A5 Price Tracker Performance (MEDIUM)

**Analysis:**
O(unique_mints) sequential `await`.
- 100 mints @ 200ms = 20s.
- 500 mints @ 200ms = 100s (Exceeds 60s loop interval).
**Verdict:** `asyncio.gather` with a semaphore is required for production scaling beyond ~200 unique tokens.

---

## Updated Release Recommendation: **BLOCKED**
The PnL calculation error is a fundamental integrity failure that invalidates all current validation metrics.
