import pytest

from app.services.safety.execution_safety_gate import (
    ExecutionSafetyGate,
    ExecutionContext,
)


def gate() -> ExecutionSafetyGate:
    g = ExecutionSafetyGate()
    g.reset_metrics()
    return g


# ── 1. Position size limit enforcement ────────────────────


def test_blocks_position_size_over_10():
    g = gate()
    ctx = ExecutionContext(position_size_eur=15.0, portfolio_exposure=0.05, drawdown=0.0)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("POSITION_SIZE" in r for r in d.reason)
    assert d.risk_level == "BLOCKED"


def test_allows_position_size_at_10():
    g = gate()
    ctx = ExecutionContext(position_size_eur=10.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80)
    d = g.validate(ctx)
    assert d.allowed
    assert d.risk_level == "LOW"


def test_allows_position_size_under_10():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80)
    d = g.validate(ctx)
    assert d.allowed


# ── 2. Exposure limit enforcement ─────────────────────────


def test_blocks_exposure_over_0_15():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.20, drawdown=0.0)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("EXPOSURE" in r for r in d.reason)


def test_allows_exposure_at_0_15():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.15, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80)
    d = g.validate(ctx)
    assert d.allowed


# ── 3. Drawdown limit enforcement ─────────────────────────


def test_blocks_drawdown_at_0_15():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.15)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("DRAWDOWN" in r for r in d.reason)


def test_blocks_drawdown_over_0_15():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.30)
    d = g.validate(ctx)
    assert not d.allowed


def test_allows_drawdown_below_0_15():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.14,
                           regime_confidence=0.8, stability_score=80)
    d = g.validate(ctx)
    assert d.allowed


# ── 4. Control layer blocking (stability_score) ───────────


def test_blocks_low_stability():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           stability_score=30)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("STABILITY_SCORE" in r for r in d.reason)


def test_allows_high_stability():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           stability_score=80, regime_confidence=0.8)
    d = g.validate(ctx)
    assert d.allowed


def test_blocks_exactly_49_stability():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           stability_score=49)
    d = g.validate(ctx)
    assert not d.allowed


# ── 5. Drift-based blocking ───────────────────────────────


def test_blocks_high_drift():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           drift_score=75, stability_score=80, regime_confidence=0.8)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("DRIFT_SCORE" in r for r in d.reason)


def test_allows_low_drift():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           drift_score=10, stability_score=80, regime_confidence=0.8)
    d = g.validate(ctx)
    assert d.allowed


def test_zero_drift_not_blocked():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           drift_score=0.0, stability_score=80, regime_confidence=0.8)
    d = g.validate(ctx)
    assert d.allowed


# ── 6. Regime confidence gate ─────────────────────────────


def test_blocks_low_regime_confidence():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.3, stability_score=80)
    d = g.validate(ctx)
    assert not d.allowed
    assert any("REGIME_CONFIDENCE" in r for r in d.reason)


def test_allows_high_regime_confidence():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80)
    d = g.validate(ctx)
    assert d.allowed


# ── 6. Risk flags blocking ────────────────────────────────


@pytest.mark.parametrize("flag", ["CONTROL_FAILURE", "DATA_UNAVAILABLE", "REGIME_UNSTABLE", "KILL_SWITCH_ACTIVE"])
def test_blocks_critical_risk_flag(flag):
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80,
                           risk_flags=[flag])
    d = g.validate(ctx)
    assert not d.allowed
    assert any("RISK_FLAG" in r for r in d.reason)


def test_allows_unknown_risk_flag():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80,
                           risk_flags=["UNKNOWN_FLAG"])
    d = g.validate(ctx)
    assert d.allowed


# ── 7. Kill switch fail-closed behavior ───────────────────


def test_kill_switch_flag_blocks():
    """The KILL_SWITCH_ACTIVE risk flag blocks trades."""
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                           regime_confidence=0.8, stability_score=80,
                           risk_flags=["KILL_SWITCH_ACTIVE"])
    d = g.validate(ctx)
    assert not d.allowed


def test_missing_safety_signals_fail_closed():
    """If all safety signals are missing (defaults), trade must be blocked."""
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0)
    d = g.validate(ctx)
    assert not d.allowed, (
        "Missing safety signals (regime_confidence=0, stability_score=0) must block"
    )


# ── 8. Deterministic outputs for same input ───────────────


def test_deterministic():
    g = gate()
    ctx = ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.10,
                           regime_confidence=0.8, stability_score=80, drift_score=10)
    r1 = g.validate(ctx)
    r2 = g.validate(ctx)
    assert r1.allowed == r2.allowed
    assert r1.reason == r2.reason
    assert r1.risk_level == r2.risk_level


def test_deterministic_blocked():
    g = gate()
    ctx = ExecutionContext(position_size_eur=20.0, portfolio_exposure=0.30, drawdown=0.25,
                           regime_confidence=0.3, stability_score=20, drift_score=90,
                           risk_flags=["CONTROL_FAILURE"])
    r1 = g.validate(ctx)
    r2 = g.validate(ctx)
    assert r1.allowed == r2.allowed
    assert r1.reason == r2.reason
    assert r1.risk_level == r2.risk_level
    assert not r1.allowed


# ── Metrics snapshot ──────────────────────────────────────


def test_metrics_snapshot():
    g = gate()
    g.validate(ExecutionContext(position_size_eur=20.0, portfolio_exposure=0.05, drawdown=0.0))
    g.validate(ExecutionContext(position_size_eur=5.0, portfolio_exposure=0.05, drawdown=0.0,
                                regime_confidence=0.8, stability_score=80))
    snap = g.get_metrics_snapshot()
    assert snap["execution_blocks_total"] >= 1
    assert snap["execution_allowed_total"] >= 1
    assert "POSITION_SIZE" in snap["execution_block_reason_counter"]
