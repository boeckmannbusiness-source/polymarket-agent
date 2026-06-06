# Micro-Capital Deployment Protocol — Compliance Audit

**Date**: 2026-06-05
**Audited by**: OpenCode System Audit
**System**: polymarket-intelligence-agent v0.1.0

---

## 1. Protocol Compliance Matrix

### 1a. Execution Safety Layer

| Requirement | Status | Details |
|---|---|---|
| Max position size (5-10€) | **PARTIAL** | `GlobalRiskGuard` enforces `MAX_POSITION_SIZE_PCT=0.002` → $20 at $10k capital (fallback min $2). `MICRO_LIVE_SAFE_MODE` caps at $1. No config for 5-10€ target directly. |
| Max portfolio exposure (50-100€) | **PARTIAL** | `GlobalRiskGuard` enforces `MAX_TOTAL_EXPOSURE_PCT=0.02` → $200 (fallback $20). `SafetyService` has `max_total_exposure=$50k`. Limits exist but not aligned to protocol. |
| Max open positions (3) | **IMPLEMENTED** | `GlobalRiskGuard.MAX_OPEN_POSITIONS=3` at code level, `RiskService` reads `settings.MAX_OPEN_POSITIONS=5` — **discrepancy** (3 vs 5). |
| Kill switch (-15% drawdown) | **PARTIAL** | `ModeManager` triggers PROTECTED at drawdown > 15%. But `RiskOverlay` uses 20%/12%, `SystemHealthStore` alerts at 15%, `LiveTradingStateMachine` uses 2% daily. **Inconsistent thresholds across layers.** |
| No leverage | **IMPLEMENTED** | Platform-native (Polymarket CLOB has no leverage). |

### 1b. Control Layer Enforcement (4G)

| Requirement | Status | Details |
|---|---|---|
| ControlPlane actively gates execution | **IMPLEMENTED** | `ExecutionService._check_safety()` calls `control_plane.is_trading_enabled()`, `is_strategy_paused()`, `is_market_paused()`. |
| Drift detector blocks trades | **MISSING** | `PortfolioDriftDetector` runs daily (24h cycle) via `AutonomousControlPipeline`. Output is analytical-only — NEVER checked in the trade execution path. |
| EMA smoothing before execution | **MISSING** | `StabilityController` applies EMA smoothing to weights, but only in the 24h pipeline. `TradeService.create_trade()` pulls raw weights from `PortfolioAllocator`, NOT stabilized weights from control layer. |
| Regime transition control gates execution | **MISSING** | `RegimeTransitionController` stabilizes regime probabilities but output is never consumed by execution path. |

### 1c. Optimization Constraints (4F)

| Requirement | Status | Details |
|---|---|---|
| Tier caps enforced at runtime | **PARTIAL** | `PortfolioAllocator.allocate()` applies caps. But no re-validation of optimizer output before execution — optimizer output flows directly through allocator without a separate gate. |
| Optimizer output revalidated | **MISSING** | No cross-validation gate between optimization output and trade execution. |

### 1d. Decision Logging Integrity

| Requirement | Status | Details |
|---|---|---|
| Regime state logged | **PARTIAL** | `ExecutionTrace.signal_payload` may contain regime, but not forced. No dedicated field. |
| Confidence score logged | **PARTIAL** | In `signal_payload` but not as a first-class field. |
| Risk score logged | **IMPLEMENTED** | `ExecutionTrace.risk_approved` and `risk_reason`. |
| Control adjustment logged | **MISSING** | No control layer adjustment data in any execution trace. |
| Final execution reason | **IMPLEMENTED** | `Trade.reason` field captures the trigger reason. |

### 1e. Kill Switch Real Activation Path

| Requirement | Status | Details |
|---|---|---|
| Manual trigger | **IMPLEMENTED** | Two paths: `/debug/kill-switch/enable` API (via `FORCE_TRADING_DISABLED`), and `SafetyService.set_kill_switch()` (DB persisted). |
| Automatic trigger (drawdown) | **PARTIAL** | `ModeManager` evaluates every 15s, can trigger PROTECTED at >15% drawdown. `RiskOverlay` checks every 30s at 20%. `LiveTradingStateMachine` at 120s using 2% daily. |
| Propagation delay | **OK** | Kill switch checked at start of `TradeService.create_trade()` and in `ExecutionService._check_safety()`. Max delay = eval interval (15-30s). |
| Redis dependency = fail-open | **CRITICAL** | `trade_service.py:72-76`: Redis failure logs warning but **continues trading**. `control_plane.py:33-39`: Falls back to local state. Remote kill switch is NOT enforceable when Redis is down. |
| Consistency across layers | **FRAGILE** | 3 independent kill switch mechanisms (module flag, instance flag, Redis remote). No single source of truth. |

---

## 2. Gap List

### CRITICAL Gaps (must fix before deployment)

| Gap | Location | Impact | Test Evidence |
|---|---|---|---|
| **Redis failure → fail-open** | `trade_service.py:72-76` | Remote kill switch unenforceable when Redis is down | `test_kill_switch_redis_failure_is_fail_open` |
| **Drift detector not gating execution** | `services/control/portfolio_drift_detector.py` | System can trade into diverging allocations without control layer intervention | `test_drift_detection_not_blocking_execution` |
| **Control pipeline outputs not consumed** | `services/control/autonomous_control_pipeline.py` | EMA smoothing, regime stabilization, drift detection are analytical-only | Code analysis |
| **Inconsistent drawdown thresholds** | Multiple files | `ModeManager` uses 15%, `RiskOverlay` uses 20%/12%, `HealthStore` alerts at 15%, `StateMachine` uses 2% daily | Code analysis |

### MODERATE Gaps

| Gap | Location | Impact |
|---|---|---|
| **Position limit discrepancy** | `global_risk_guard.py:18` (3) vs `risk_service.py:64` (settings.MAX_OPEN_POSITIONS=5) | Inconsistent constraints between validation layers |
| **No portfolio-level exposure check** | Risk checks are per-trade only | System lacks a pre-trade portfolio exposure sanity check against protocol limits |
| **Decision logging incomplete** | `execution_trace.py` | Missing: regime state, control adjustment, optimizer output as first-class fields |
| **SystemMode.can_execute_trades() too restrictive** | `system_mode.py:322` | Only NORMAL mode allows trades. PROTECTED mode (on drawdown >15%) blocks all — no intermediate REDUCED state for trading |

### Design-Only (exist in schema/model but not enforced at runtime)

| Component | File | What's missing |
|---|---|---|
| Stability constraints | `services/control/stability_controller_service.py` | EMA smoothing runs on 24h cycle, never applied to real-time execution path |
| Drift detection | `services/control/portfolio_drift_detector.py` | Generates reports but never gates trades |
| Regime transition control | `services/control/regime_transition_controller.py` | Stabilizes regime probabilities, output ignored by execution |
| Circuit breaker actions | `services/risk/circuit_breakers.py:156-172` | Check functions are stubs (`return False, ""`), never actually evaluate conditions |

---

## 3. Runtime Risk Assessment

```
╔══════════════════════════════════════════════════════════╗
║            RUNTIME RISK: CONDITIONALLY SAFE              ║
╚══════════════════════════════════════════════════════════╝
```

### Why CONDITIONALLY SAFE and not SAFE

**Safe behaviors (verified by tests):**
- ✅ Max position size enforced by `GlobalRiskGuard`
- ✅ Max open positions (3) enforced
- ✅ Kill switch blocks all trades when active
- ✅ Control plane disables trading on command
- ✅ Mode manager blocks execution on drawdown >15%
- ✅ Execution service checks control plane before every trade
- ✅ Emergency stop cancels all open/pending trades

**Unsafe behaviors (verified by tests):**
- ❌ Redis failure → kill switch is bypassed (fail-open)
- ❌ Drift detector never consulted during execution
- ❌ Control layer (4G) outputs are analytical-only
- ❌ Decision logging misses regime, control, and optimization context

### Condition for reaching SAFE

Fix in priority order:
1. Make Redis kill switch check fail-closed (raise error, not warn)
2. Add execution gate that checks drift score + stability score before trade approval
3. Add pre-trade portfolio exposure check against protocol-defined 50-100€/5-10€ limits
4. Connect control pipeline outputs (stabilized weights, smoothed regimes) to the execution path
5. Add regime, control adjustment, and optimization output to `ExecutionTrace` as first-class fields

---

## 4. Test Harness Summary

**File**: `backend/app/tests/test_protocol_enforcement.py`
**Tests**: 12 passing

| Test | What it verifies | Protocol Requirement |
|---|---|---|
| `test_over_exposure_10eur_rule_enforced` | Rejects >10€ trade | Max position size |
| `test_under_exposure_allowed` | Allows compliant trade | Positive test |
| `test_max_open_positions_enforced` | Rejects 4th position | Max 3 positions |
| `test_control_plane_blocks_trades_when_disabled` | Control plane gates execution | Control layer active |
| `test_mode_manager_blocks_execution_on_drawdown_breach` | 15% drawdown blocks trades | Kill switch |
| `test_execution_service_checks_control_plane` | Execution safety check | Control layer |
| `test_safety_service_kill_switch_blocks` | Kill switch blocks all trades | Kill switch |
| `test_drift_detection_not_blocking_execution` | **GAP** — drift not gating | Control layer enforcement |
| `test_kill_switch_redis_failure_is_fail_open` | **GAP** — Redis failure bypasses kill switch | Kill switch reliability |
| `test_kill_switch_automatic_trigger_path` | Auto trigger path works | Kill switch |
| `test_kill_switch_manual_emergency_stop` | Manual emergency stop cancels trades | Kill switch |
| `test_trade_decision_logging_contains_required_fields` | Decision logging completeness | Logging integrity |

---

## 5. Immediate Action Items

```
P0: Make kill switch Redis check fail-closed (raise, don't log)
P0: Add drift/stability check to ExecutionGate before trade approval
P1: Unify drawdown thresholds across all layers (single source: 15%)
P1: Add pre-trade portfolio exposure check against protocol limits
P1: Populate ExecutionTrace with regime, control, optimization data
P2: Connect control pipeline stabilized weights to PortfolioAllocator
P2: Reconcile MAX_OPEN_POSITIONS (3 vs 5) across layers
P3: Implement real check functions in circuit breakers (stubs currently)
```
