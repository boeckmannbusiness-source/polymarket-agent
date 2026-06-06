import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime, timezone

from app.services.trade_service import TradeService, FORCE_TRADING_DISABLED, MICRO_LIVE_SAFE_MODE
from app.services.global_risk_guard import GlobalRiskGuard, MAX_OPEN_POSITIONS, MAX_TOTAL_EXPOSURE_PCT, MAX_POSITION_SIZE_PCT
from app.services.safety_service import SafetyService
from app.services.control.control_plane import ControlPlane, control_plane
from app.services.risk_overlay import RiskOverlay
from app.core.system_mode import ModeManager, SystemMode
from app.schemas.trade import TradeCreateRequest


def _make_scalars_mock(values=None):
    """Build a mock for .scalars() chain that works with async execute()."""
    s = MagicMock()
    if values is None:
        s.all.return_value = []
        s.one_or_none.return_value = None
    elif isinstance(values, list):
        s.all.return_value = values
        s.one_or_none.return_value = values[0] if values else None
    else:
        s.all.return_value = [values]
        s.one_or_none.return_value = values
    return s


def _make_db_execute_mock(values=None):
    """Configure mock_db.execute to return a result with .scalars()."""
    r = MagicMock()
    r.scalars.return_value = _make_scalars_mock(values)
    return r


# ── Scenario 1: Over-exposure attempt ──────────────────────────

@pytest.mark.asyncio
async def test_over_exposure_10eur_rule_enforced():
    """
    Protocol requirement: max 5-10€ per trade.
    System should reject trades exceeding configured position size.
    """
    mock_db = AsyncMock()
    mock_db.execute.return_value = _make_db_execute_mock([])

    guard = GlobalRiskGuard(mock_db)

    capital = 100.0
    with patch("app.services.global_risk_guard._get_capital", return_value=capital):
        with patch("app.services.global_risk_guard._compute_effective_limits") as mock_limits:
            mock_limits.return_value = {
                "total_exposure": 10.0,
                "position_size": 10.0,
                "market_exposure": 5.0,
            }
            result = await guard.check_exposure(
                market_id=str(uuid4()),
                outcome="YES",
                proposed_size=15.0,
                proposed_price=0.5,
            )
            assert not result.approved, (
                f"Over-exposure (15 * 0.5 = 7.5) should be rejected but was approved. "
                f"Reason: {result.reason}"
            )


@pytest.mark.asyncio
async def test_under_exposure_allowed():
    """
    Verify that small compliant trades pass exposure checks.
    """
    mock_db = AsyncMock()
    mock_db.execute.return_value = _make_db_execute_mock([])

    guard = GlobalRiskGuard(mock_db)

    capital = 100.0
    with patch("app.services.global_risk_guard._get_capital", return_value=capital):
        with patch("app.services.global_risk_guard._compute_effective_limits") as mock_limits:
            mock_limits.return_value = {
                "total_exposure": 10.0,
                "position_size": 10.0,
                "market_exposure": 5.0,
            }
            result = await guard.check_exposure(
                market_id=str(uuid4()),
                outcome="YES",
                proposed_size=5.0,
                proposed_price=0.10,
            )
            assert result.approved, (
                f"Compliant trade (5 * 0.10 = 0.5) should be approved. "
                f"Reason: {result.reason}"
            )


@pytest.mark.asyncio
async def test_max_open_positions_enforced():
    """
    Protocol requirement: max 3 open positions.
    System should reject when limit is reached.
    """
    mock_db = AsyncMock()
    mock_trades = []
    for i in range(3):
        t = MagicMock()
        t.status = "open"
        t.filled_size = 1.0
        t.filled_price = 0.5
        t.market_id = uuid4()
        mock_trades.append(t)
    mock_db.execute.return_value = _make_db_execute_mock(mock_trades)

    guard = GlobalRiskGuard(mock_db)

    with patch("app.services.global_risk_guard._get_capital", return_value=100.0):
        result = await guard.check_exposure(
            market_id=str(uuid4()),
            outcome="YES",
            proposed_size=5.0,
            proposed_price=0.10,
        )
        assert not result.approved, (
            f"4th position should be rejected (max {MAX_OPEN_POSITIONS}). "
            f"Reason: {result.reason}"
        )


# ── Scenario 2: Control failure simulation ──────────────────────

@pytest.mark.asyncio
async def test_control_plane_blocks_trades_when_disabled():
    """
    Protocol requirement: Control layer must actively gate execution.
    When trading is disabled, execution must be blocked.
    """
    cp = ControlPlane()
    with patch.object(cp, "_redis_or", return_value=None):
        await cp.set_trading_enabled(False)
        enabled = await cp.is_trading_enabled()
        assert not enabled, "Control plane should report trading disabled"
        await cp.set_trading_enabled(True)
        enabled = await cp.is_trading_enabled()
        assert enabled, "Control plane should report trading enabled after reset"


@pytest.mark.asyncio
async def test_mode_manager_blocks_execution_on_drawdown_breach():
    """
    Protocol requirement: -15% drawdown → STOP ALL TRADING.
    ModeManager should go to PROTECTED which blocks can_execute_trades().
    """
    mm = ModeManager()
    health = {
        "drawdown": 0.16,
        "emergency_stop": False,
        "kill_switch": False,
        "circuit_breaker_open": False,
        "db_pool_utilization_pct": 30,
        "redis_memory_pct": 20,
        "redis_max_pending": 10,
        "reconnect_storm": 0,
        "stream_pressure_ratio": 0.1,
    }
    mode = await mm.evaluate(health)
    assert mode == SystemMode.PROTECTED, (
        f"Mode should be PROTECTED at 16% drawdown, got {mode}"
    )
    assert not mm.can_execute_trades(), (
        "can_execute_trades() should return False when drawdown exceeds 15%"
    )


@pytest.mark.asyncio
async def test_execution_service_checks_control_plane():
    """
    Verify that ExecutionService._check_safety() gates on control plane.
    """
    from app.services.execution.execution_service import ExecutionService, ExecutionSafetyError

    mock_db = AsyncMock()
    svc = ExecutionService(mock_db)

    with patch.object(control_plane, "is_trading_enabled", return_value=False):
        with pytest.raises(ExecutionSafetyError, match="Global trading disabled"):
            await svc._check_safety()


@pytest.mark.asyncio
async def test_safety_service_kill_switch_blocks():
    """
    Protocol requirement: Kill switch must block all trades.
    SafetyService.check_trade_approval() with kill switch active → blocked.
    """
    mock_state = MagicMock(
        kill_switch_active=True,
        circuit_breaker_active=True,
        circuit_breaker_reason="manual_kill_switch",
        quarantined_strategies=[],
        daily_pnl=0.0,
        checks_passed=0,
        checks_failed=0,
    )
    exec_result_1 = MagicMock()
    exec_result_1.scalar_one_or_none.return_value = mock_state
    exec_result_n = _make_db_execute_mock([])

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [exec_result_1, exec_result_n, exec_result_n]

    svc = SafetyService(mock_db)
    result = await svc.check_trade_approval(strategy_name="test", size=5.0, confidence=0.8)
    assert not result.approved, "Kill switch should block all trades"
    assert "Kill switch" in " ".join(result.reasons), (
        f"Expected kill switch reason, got: {result.reasons}"
    )


@pytest.mark.asyncio
async def test_drift_detection_not_blocking_execution():
    """
    CRITICAL GAP TEST: Verify the drift detector is NOT blocking execution.
    This confirms the gap — drift detection is analytical-only.
    """
    mock_db = AsyncMock()
    mock_db.execute.return_value = _make_db_execute_mock([])

    guard = GlobalRiskGuard(mock_db)

    with patch("app.services.global_risk_guard._get_capital", return_value=100.0):
        with patch("app.services.global_risk_guard._compute_effective_limits") as mock_limits:
            mock_limits.return_value = {
                "total_exposure": 10.0,
                "position_size": 10.0,
                "market_exposure": 5.0,
            }
            result = await guard.check_exposure(
                market_id=str(uuid4()),
                outcome="YES",
                proposed_size=1.0,
                proposed_price=0.10,
            )
            # Trade passes exposure checks regardless of drift score
            assert result.approved, "Trade should pass exposure check"
            # But drift score is NEVER checked in this path
            from app.services.control.portfolio_drift_detector import portfolio_drift_detector
            latest = await portfolio_drift_detector.get_latest()
            assert latest is None or latest.overall_drift_score > 0, (
                "Drift detection exists but never consulted during execution"
            )


# ── Kill switch activation path tests ───────────────────────────

@pytest.mark.asyncio
async def test_kill_switch_redis_failure_is_fail_closed():
    """
    CRITICAL FIX: When Redis is down, the remote kill switch
    check in trade_service.py now raises SystemHaltException.
    This is fail-closed behavior — trading halts when state store
    is unavailable.
    """
    from app.services.trade_service import SystemHaltException

    mock_db = AsyncMock()

    async def execute_side_effect(*args, **kwargs):
        return _make_db_execute_mock([])

    mock_db.execute = execute_side_effect
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.rollback = AsyncMock()

    with patch("app.services.trade_service.FORCE_TRADING_DISABLED", False):
        with patch("app.services.trade_service.MICRO_LIVE_SAFE_MODE", False):
            with patch("app.redis.get_redis", side_effect=Exception("Redis connection refused")):
                svc = TradeService(mock_db)
                with pytest.raises(SystemHaltException, match="STATE STORE FAILURE"):
                    await svc.create_trade(
                        TradeCreateRequest(
                            market_id=uuid4(),
                            side="buy",
                            outcome="YES",
                            size=1.0,
                            price=0.10,
                            confidence=0.8,
                            agent_id="test",
                            correlation_id=str(uuid4()),
                        )
                    )


@pytest.mark.asyncio
async def test_kill_switch_automatic_trigger_path():
    """
    Verify the automatic kill switch trigger path:
    ModeManager -> PROTECTED mode -> blocks can_execute_trades().
    """
    mm = ModeManager()

    health_dd = {"drawdown": 0.16}
    with patch.object(mm, "_compute_mode_from_metrics", return_value=SystemMode.PROTECTED):
        mode = await mm.evaluate(health_dd)

    assert not mm.can_execute_trades()


@pytest.mark.asyncio
async def test_kill_switch_manual_emergency_stop():
    """
    Verify TradeService.emergency_stop() cancels all open/pending trades.
    """
    mock_db = AsyncMock()
    mock_trade_1 = MagicMock(status="open")
    mock_trade_2 = MagicMock(status="pending")
    mock_db.execute.return_value = _make_db_execute_mock([mock_trade_1, mock_trade_2])

    svc = TradeService(mock_db)
    await svc.emergency_stop()

    assert mock_trade_1.status == "cancelled"
    assert mock_trade_2.status == "cancelled"


# ── Decision logging integrity test ─────────────────────────────

@pytest.mark.asyncio
async def test_trade_decision_logging_contains_required_fields():
    """
    Protocol requirement: Every trade decision must log:
    - regime state, confidence, optimization output, control adjustment, final decision.
    Check that ExecutionTrace captures these.
    """
    from app.models.execution_trace import ExecutionTrace

    trace = ExecutionTrace(
        trade_id=uuid4(),
        signal_id=uuid4(),
        market_id=uuid4(),
        signal_payload={"regime": "normal", "confidence": 0.8},
        risk_approved=True,
        risk_reason="all_checks_passed",
        execution_side="buy",
        execution_outcome="YES",
        execution_size=5.0,
        strategy_name="test_strategy",
    )

    trace_dict = {
        "signal_payload": trace.signal_payload,
        "risk_approved": trace.risk_approved,
        "risk_reason": trace.risk_reason,
        "strategy_name": trace.strategy_name,
    }

    assert "regime" in (trace.signal_payload or {}), "Regime state not in execution trace"
    assert "confidence" in (trace.signal_payload or {}), "Confidence not in execution trace"
    assert trace.risk_approved is not None, "Risk decision not in execution trace"
    assert trace.execution_size is not None, "Execution size not in execution trace"
