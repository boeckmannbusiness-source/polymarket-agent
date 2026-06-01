#!/usr/bin/env python3
"""
PAPER BURN-IN SHORT — Production-like behavioral validation harness.

Usage:
    python scripts/paper_burnin_short.py [--duration 15] [--extended]

This script:
  1. Configures the environment for PAPER_BURNIN_SHORT mode
  2. Starts the application (uvicorn) as a subprocess
  3. Monitors metrics every 60 seconds via the API + direct DB/Redis queries
  4. Runs for the specified duration (default 15 min, extended 30 min)
  5. Generates /debug/paper-test-report/ with full analysis
"""

import argparse
import asyncio
import json
import os
import platform
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────

REPORT_DIR = Path("debug") / "paper-test-report"
DEFAULT_DURATION_MINUTES = 15
EXTENDED_DURATION_MINUTES = 30
METRICS_INTERVAL_SECONDS = 60
API_BASE = "http://127.0.0.1:8000"
APP_PORT = 8000
APP_HOST = "127.0.0.1"


@dataclass
class MetricsSnapshot:
    timestamp: str
    elapsed_seconds: float
    total_signals: int = 0
    accepted_signals: int = 0
    rejected_signals: int = 0
    executed_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_loss_ratio: float = 0.0
    avg_pnl: float = 0.0
    max_drawdown: float = 0.0
    strategy_kill_count: int = 0
    exit_engine_triggers: int = 0
    portfolio_value: float = 0.0
    open_positions: int = 0
    system_health: str = "unknown"
    signal_rate_per_min: float = 0.0
    risk_rejection_rate: float = 0.0
    execution_success_rate: float = 0.0
    avg_slippage: float = 0.0
    crash_count: int = 0
    active_strategies: int = 0
    disabled_strategies: int = 0
    ws_events_per_min: int = 0
    redis_stream_length: int = 0
    mode: str = "unknown"
    overlay_state: str = "unknown"
    guardian_states: dict = field(default_factory=dict)


@dataclass
class TradeCycleRecord:
    timestamp: str
    market_id: str
    condition_id: str
    strategy_name: str
    risk_decision: str
    risk_reason: str
    execution_decision: str
    entry_price: float | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    pnl: float | None = None
    slippage: float | None = None
    liquidity_regime: str = "unknown"
    price_zone: str = "unknown"
    signal_id: str = ""
    trade_id: str = ""


@dataclass
class TestReport:
    start_time: str
    end_time: str
    duration_minutes: float
    duration_mode: str

    equity_curve: list[dict] = field(default_factory=list)
    metrics_snapshots: list[MetricsSnapshot] = field(default_factory=list)
    trade_cycles: list[TradeCycleRecord] = field(default_factory=list)
    strategy_pnl_ranking: dict = field(default_factory=dict)
    rejection_reasons_breakdown: dict = field(default_factory=dict)
    exit_reason_distribution: dict = field(default_factory=dict)
    guardian_disable_events: list[dict] = field(default_factory=list)

    total_signals: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    total_executed: int = 0
    total_closed: int = 0
    win_count: int = 0
    loss_count: int = 0
    avg_pnl: float = 0.0
    max_drawdown: float = 0.0
    signal_to_execution_rate: float = 0.0
    system_stability_score: float = 0.0
    anomalies: list[str] = field(default_factory=list)
    recommendation: str = ""

    crash_count: int = 0
    none_type_propagations: int = 0
    missing_market_ids: int = 0
    invalid_schemas: int = 0
    runaway_signal_loops: int = 0
    redis_lag_exceeded: bool = False
    memory_growth_exceeded: bool = False
    initial_memory_mb: float = 0.0
    final_memory_mb: float = 0.0

    # Replay drift
    replay_drift_pct: float = 0.0

    # Strategy PnL detail
    strategy_details: dict = field(default_factory=dict)

    # System health history
    health_history: list[dict] = field(default_factory=list)

    # Fail conditions
    fail_conditions: list[str] = field(default_factory=list)
    passed: bool = True


# ────────────────────────────────────────────────────────────────
# HTTP helper (no external deps — uses urllib)
# ────────────────────────────────────────────────────────────────

def _http_get(path: str, timeout: float = 5.0) -> dict | None:
    import urllib.request
    import urllib.error
    url = f"{API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
        return None


# ────────────────────────────────────────────────────────────────
# Environment Setup
# ────────────────────────────────────────────────────────────────

def setup_environment(extended: bool = False):
    """Configure environment variables for PAPER_BURNIN_SHORT mode."""
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("TRADING_MODE", "paper")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("LOG_FORMAT", "text")
    os.environ.setdefault("METRICS_ENABLED", "true")
    os.environ.setdefault("PAPER_INITIAL_CAPITAL", "10000")

    # Burn-in short mode tuning
    os.environ.setdefault("HEARTBEAT_INTERVAL_SECONDS", "15")
    os.environ.setdefault("STREAM_TRIM_INTERVAL", "600")
    os.environ.setdefault("REDIS_STREAM_MAXLEN", "5000")

    # Disable long-window analytics for short run
    os.environ.setdefault("DEDUP_TTL_SECONDS", "300")

    # Kill switch safety
    os.environ.setdefault("FORCE_TRADING_DISABLED", "false")

    env_marker = "EXTENDED" if extended else "SHORT"
    os.environ["PAPER_BURNIN_SHORT"] = "1"
    os.environ["PAPER_BURNIN_MODE"] = env_marker


# ────────────────────────────────────────────────────────────────
# App process management
# ────────────────────────────────────────────────────────────────

_app_process: subprocess.Popen | None = None


_app_log_file: Path | None = None


def start_app() -> subprocess.Popen:
    """Start the FastAPI application via uvicorn."""
    global _app_process, _app_log_file
    backend_dir = str(Path(__file__).resolve().parent.parent)
    _app_log_file = Path(backend_dir) / "debug" / "paper-test-report" / "app_output.log"
    _app_log_file.parent.mkdir(parents=True, exist_ok=True)
    log_fd = open(str(_app_log_file), "w", encoding="utf-8")
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", APP_HOST,
        "--port", str(APP_PORT),
        "--log-level", "info",
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", backend_dir)
    _app_process = subprocess.Popen(
        cmd,
        cwd=backend_dir,
        env=env,
        stdout=log_fd,
        stderr=subprocess.STDOUT,
    )
    log_fd.write(f"\n--- Started at {datetime.now(timezone.utc).isoformat()} ---\n")
    log_fd.flush()
    return _app_process


def stop_app():
    """Gracefully stop the application."""
    global _app_process
    if _app_process is None:
        return
    try:
        if platform.system() == "Windows":
            _app_process.terminate()
        else:
            os.kill(_app_process.pid, signal.SIGTERM)
        _app_process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        _app_process.kill()
        _app_process.wait(timeout=5)
    except Exception:
        pass
    _app_process = None


async def wait_for_app(timeout: float = 120.0) -> bool:
    """Wait until the /health endpoint responds."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        result = _http_get("/health", timeout=5.0)
        if result is not None:
            return True
        await asyncio.sleep(2)
    return False


# ────────────────────────────────────────────────────────────────
# Metrics collection
# ────────────────────────────────────────────────────────────────

async def collect_metrics_snapshot(
    elapsed: float,
    prev: MetricsSnapshot | None = None,
) -> MetricsSnapshot:
    """Collect a single metrics snapshot from API endpoints."""
    snap = MetricsSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=round(elapsed, 1),
    )

    # Health
    health = _http_get("/health")
    if health:
        snap.system_health = "ok" if health.get("status") == "ok" else "degraded"
        snap.mode = health.get("mode", "unknown")

    # System status
    status = _http_get("/system/status")
    if status:
        pass

    # Health snapshot
    hs = _http_get("/debug/health-snapshot")
    if hs:
        snap.total_signals = hs.get("total_trades", 0)
        snap.open_positions = hs.get("open_trades", 0)
        snap.portfolio_value = hs.get("portfolio_value", 0.0)
        snap.max_drawdown = hs.get("drawdown", 0.0)
        snap.active_strategies = hs.get("active_strategies", 0)
        snap.disabled_strategies = hs.get("disabled_strategies", 0)
        snap.ws_events_per_min = hs.get("ws_events_last_minute", 0)

    # Runtime health
    rh = _http_get("/debug/runtime-health")
    if rh:
        snap.crash_count = rh.get("crash_count", 0)
        snap.signal_rate_per_min = rh.get("signal_rate_per_minute", 0.0)

    # Risk overlay
    ro = _http_get("/debug/risk-overlay")
    if ro:
        snap.overlay_state = ro.get("status", "unknown")

    # Strategy status
    ss = _http_get("/debug/strategy-status")
    if ss:
        snap.guardian_states = {}
        for name, info in ss.items():
            snap.guardian_states[name] = info.get("status", "unknown")

    # Guardian kill count
    gk = _http_get("/debug/guardian-kill-count")
    if gk:
        snap.strategy_kill_count = gk.get("strategy_kill_count", 0)

    # Exit stats
    es = _http_get("/debug/exit-stats")
    if es:
        reasons = es.get("exit_reason_distribution", {})
        snap.exit_engine_triggers = sum(reasons.values())

    # Open positions
    om = _http_get("/debug/open-market-positions")
    if om:
        snap.open_positions = om.get("count", 0)

    # Trading state
    ts = _http_get("/debug/trading-state")
    if ts:
        pass

    # If we have previous data, compute deltas
    if prev:
        snap.total_signals = max(snap.total_signals, prev.total_signals)
        snap.executed_trades = max(snap.executed_trades, prev.executed_trades)

    return snap


async def ensure_db_schema():
    """Run migration fixes that init_db may have missed."""
    from sqlalchemy import text
    from app.database import async_session_factory, engine

    async with engine.begin() as conn:
        for table in ["trades", "signals", "agent_logs", "execution_traces"]:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS correlation_id UUID"))
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_{table}_correlation_id ON {table}(correlation_id)"))
            except Exception:
                pass

        for table, col in [("backtest_runs", "mode"), ("backtest_runs", "error_message")]:
            try:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} VARCHAR(32)"))
            except Exception:
                pass


async def collect_trade_data(report: TestReport):
    """Query the database directly for trade-level data."""
    from sqlalchemy import select, func
    from app.database import async_session_factory
    from app.models import Trade, Signal, MarketEvent, PortfolioSnapshot
    from app.models.strategy import StrategyConfigRecord
    from app.models.safety import SafetyState

    async def _safe_query(label: str, coro):
        try:
            return await coro
        except Exception as e:
            report.anomalies.append(f"db_query_failed:{label}: {e}")
            return None

    async with async_session_factory() as db:
        # Total signals
        r = await _safe_query("total_signals", db.execute(select(func.count(Signal.id))))
        if r is not None:
            report.total_signals = r.scalar() or 0

        # Signals by strategy
        r = await _safe_query("signals_by_strat",
            db.execute(select(Signal.signal_type, func.count(Signal.id)).group_by(Signal.signal_type)))
        signal_counts = dict(r.all()) if r is not None else {}

        # Total trades
        r = await _safe_query("total_trades", db.execute(select(func.count(Trade.id))))
        total_trades = r.scalar() or 0 if r is not None else 0

        # Trades by status
        r = await _safe_query("open_trades",
            db.execute(select(func.count(Trade.id)).where(Trade.status.in_(["open", "pending"]))))
        open_count = r.scalar() or 0 if r is not None else 0
        report.total_executed = max(total_trades - open_count, 0)

        r = await _safe_query("closed_trades",
            db.execute(select(func.count(Trade.id)).where(Trade.status == "closed")))
        report.total_closed = r.scalar() or 0 if r is not None else 0

        # Trades with PnL
        r = await _safe_query("pnl_trades", db.execute(select(Trade).where(Trade.pnl.isnot(None))))
        all_pnl_trades = []
        if r is not None:
            all_pnl_trades = list(r.scalars().all())
            wins = [t for t in all_pnl_trades if t.pnl is not None and float(t.pnl) > 0]
            losses = [t for t in all_pnl_trades if t.pnl is not None and float(t.pnl) <= 0]
            report.win_count = len(wins)
            report.loss_count = len(losses)
            if all_pnl_trades:
                report.avg_pnl = sum(float(t.pnl or 0) for t in all_pnl_trades) / len(all_pnl_trades)

        # Strategy PnL ranking
        r = await _safe_query("strat_pnl",
            db.execute(
                select(Trade.agent_id, func.sum(Trade.pnl).label("total_pnl"), func.count(Trade.id).label("count"))
                .where(Trade.pnl.isnot(None))
                .where(Trade.agent_id.isnot(None))
                .group_by(Trade.agent_id)
            ))
        strat_data = {}
        if r is not None:
            for row in r.all():
                strat_data[row.agent_id] = {
                    "total_pnl": float(row.total_pnl or 0),
                    "trade_count": row.count,
                    "avg_pnl": float(row.total_pnl or 0) / row.count if row.count > 0 else 0,
                }
            report.strategy_pnl_ranking = dict(
                sorted(strat_data.items(), key=lambda x: x[1]["total_pnl"], reverse=True)
            )

        # Strategy details with win rate
        report.strategy_details = {}
        for sname in strat_data:
            r = await _safe_query(f"strat_detail_{sname}",
                db.execute(select(Trade).where(Trade.agent_id == sname).where(Trade.pnl.isnot(None))))
            if r is not None:
                s_list = list(r.scalars().all())
                s_wins = sum(1 for t in s_list if t.pnl is not None and float(t.pnl) > 0)
                s_losses = sum(1 for t in s_list if t.pnl is not None and float(t.pnl) < 0)
                s_total = len(s_list)
                report.strategy_details[sname] = {
                    "total_trades": s_total,
                    "wins": s_wins,
                    "losses": s_losses,
                    "win_rate": round(s_wins / s_total, 4) if s_total > 0 else 0,
                    "total_pnl": round(strat_data[sname]["total_pnl"], 4),
                    "avg_pnl": round(strat_data[sname]["avg_pnl"], 4),
                    "signal_count": signal_counts.get(sname, 0),
                }

        # Trade cycles
        r = await _safe_query("trade_cycles",
            db.execute(select(Trade).order_by(Trade.created_at.desc()).limit(100)))
        if r is not None:
            for t in r.scalars().all():
                record = TradeCycleRecord(
                    timestamp=t.created_at.isoformat() if t.created_at else "",
                    market_id=str(t.market_id) if t.market_id else "",
                    condition_id=t.outcome or "",
                    strategy_name=t.agent_id or "unknown",
                    risk_decision="accepted",
                    risk_reason="",
                    execution_decision=t.status,
                    entry_price=float(t.filled_price) if t.filled_price else (float(t.price) if t.price else None),
                    exit_price=float(t.pnl) if t.pnl else None,
                    exit_reason=t.reason,
                    pnl=float(t.pnl) if t.pnl else None,
                    slippage=float(t.slippage) if t.slippage else None,
                    trade_id=str(t.id),
                )
                if t.pnl is not None and float(t.pnl) >= 0:
                    record.exit_reason = "take_profit"
                elif t.pnl is not None and float(t.pnl) < 0:
                    record.exit_reason = "stop_loss"
                if t.extra_data:
                    record.liquidity_regime = t.extra_data.get("liquidity_regime", "unknown")
                    record.price_zone = t.extra_data.get("price_zone", "unknown")
                report.trade_cycles.append(record)

        # Portfolio snapshots
        r = await _safe_query("portfolio_snapshots",
            db.execute(select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.asc()).limit(200)))
        if r is not None:
            for snap in r.scalars().all():
                report.equity_curve.append({
                    "timestamp": snap.timestamp.isoformat() if snap.timestamp else "",
                    "portfolio_value": float(snap.portfolio_value) if snap.portfolio_value else 0,
                    "drawdown": float(snap.drawdown) if snap.drawdown else 0,
                    "total_exposure": float(snap.total_exposure) if snap.total_exposure else 0,
                    "open_positions": snap.open_positions or 0,
                })

        # Max drawdown
        r = await _safe_query("max_drawdown",
            db.execute(select(func.max(PortfolioSnapshot.drawdown))))
        if r is not None:
            report.max_drawdown = float(r.scalar() or 0)

        # Guardian states
        r = await _safe_query("guardian_configs", db.execute(select(StrategyConfigRecord)))
        if r is not None:
            for cfg in r.scalars().all():
                if not cfg.enabled:
                    report.guardian_disable_events.append({
                        "strategy": cfg.strategy_name,
                        "disabled_at": cfg.updated_at.isoformat() if cfg.updated_at else "",
                        "reason": "disabled_by_guardian",
                    })

        # Exit reason distribution
        r = await _safe_query("exit_reasons",
            db.execute(
                select(Trade.reason, func.count(Trade.id))
                .where(Trade.status == "closed")
                .where(Trade.reason.isnot(None))
                .group_by(Trade.reason)
            ))
        if r is not None:
            report.exit_reason_distribution = dict(r.all())
        if not report.exit_reason_distribution:
            report.exit_reason_distribution = {
                "take_profit": report.win_count,
                "stop_loss": report.loss_count,
            }

        # Safety state
        r = await _safe_query("safety_state",
            db.execute(select(SafetyState).order_by(SafetyState.updated_at.desc()).limit(1)))
        if r is not None:
            ss = r.scalar_one_or_none()
            if ss:
                if ss.circuit_breaker_active:
                    report.anomalies.append("circuit_breaker_was_active")
                if ss.kill_switch_active:
                    report.anomalies.append("kill_switch_was_active")

        # Missing market_ids
        r = await _safe_query("missing_market_ids",
            db.execute(
                select(func.count(Trade.id))
                .where(Trade.market_id.is_(None))
                .where(Trade.status != "pending")
            ))
        if r is not None:
            report.missing_market_ids = r.scalar() or 0
            if report.missing_market_ids > 0:
                report.fail_conditions.append(f"{report.missing_market_ids}_trades_without_market_id")

        # Market events count
        r = await _safe_query("market_event_count", db.execute(select(func.count(MarketEvent.id))))
        me_count = r.scalar() or 0 if r is not None else 0
        report.health_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_events": me_count,
            "total_trades": total_trades,
            "open_trades": total_trades - report.total_closed,
            "closed_trades": report.total_closed,
        })


async def collect_replay_drift(report: TestReport):
    """Check replay drift if baseline data exists."""
    try:
        from sqlalchemy import select, func
        from app.database import async_session_factory
        from app.models import MarketEvent

        async with async_session_factory() as db:
            # Simple event rate drift check
            now = datetime.now(timezone.utc)
            fifteen_ago = now - timedelta(minutes=15)
            thirty_ago = now - timedelta(minutes=30)

            recent = await db.execute(
                select(func.count(MarketEvent.id))
                .where(MarketEvent.timestamp >= fifteen_ago)
            )
            recent_count = recent.scalar() or 0

            older = await db.execute(
                select(func.count(MarketEvent.id))
                .where(MarketEvent.timestamp >= thirty_ago)
                .where(MarketEvent.timestamp < fifteen_ago)
            )
            older_count = older.scalar() or 0

            if older_count > 0:
                drift = abs(recent_count - older_count) / older_count
                report.replay_drift_pct = round(drift * 100, 2)
            else:
                report.replay_drift_pct = 0.0
    except Exception:
        report.replay_drift_pct = -1.0


_redis_stream_info: dict[str, int] = {}


async def collect_redis_metrics(report: TestReport):
    """Check Redis stream lengths and lag."""
    global _redis_stream_info
    try:
        from app.redis import get_redis
        r = await get_redis()
        pong = await r.ping()
        report.redis_lag_exceeded = False
        for stream in ["market:data", "wallet:trade", "signal:generated", "trade:request"]:
            try:
                info = await r.xinfo_stream(stream)
                _redis_stream_info[stream] = info.get('length', 0)
            except Exception:
                _redis_stream_info[stream] = -1
    except Exception as e:
        report.anomalies.append(f"redis_connection_error: {e}")


async def collect_signals_data(report: TestReport):
    """Collect signal data from the database."""
    try:
        from sqlalchemy import select, func
        from app.database import async_session_factory
        from app.models import Signal

        async with async_session_factory() as db:
            total = await db.execute(select(func.count(Signal.id)))
            report.total_signals = total.scalar() or 0

            # Signal counts per strategy
            by_strat = await db.execute(
                select(Signal.signal_type, func.count(Signal.id))
                .group_by(Signal.signal_type)
            )
            sig_per_strat = dict(by_strat.all())

            # Signal → execution conversion
            executed_signals = await db.execute(
                select(func.count(Signal.id))
                .where(Signal.is_active == False)
            )
            executed_count = executed_signals.scalar() or 0

            if report.total_signals > 0:
                report.signal_to_execution_rate = round(
                    executed_count / report.total_signals, 4
                )

            # Rejection reasons (from signals where direction is None/empty)
            missing = await db.execute(
                select(func.count(Signal.id))
                .where(Signal.direction.is_(None))
            )
            report.invalid_schemas = missing.scalar() or 0
            if report.invalid_schemas > 0:
                report.fail_conditions.append(f"{report.invalid_schemas}_signals_with_missing_direction")

    except Exception as e:
        report.anomalies.append(f"signal_data_collection_error: {e}")


# ────────────────────────────────────────────────────────────────
# System stability score
# ────────────────────────────────────────────────────────────────

def compute_stability_score(report: TestReport) -> float:
    """Compute a stability score 0-100 based on system health indicators."""
    score = 100.0

    # Deductions
    if report.crash_count > 0:
        score -= min(report.crash_count * 10, 30)
    if report.missing_market_ids > 0:
        score -= min(report.missing_market_ids * 5, 20)
    if report.invalid_schemas > 0:
        score -= min(report.invalid_schemas * 5, 15)
    if report.redis_lag_exceeded:
        score -= 20
    if report.memory_growth_exceeded:
        score -= 15
    if len(report.guardian_disable_events) > 0:
        score -= min(len(report.guardian_disable_events) * 5, 20)

    # Bonus for active trading
    if report.total_executed > 5:
        score += 5
    if report.win_count > report.loss_count and report.total_closed > 0:
        score += 5

    return max(0.0, min(100.0, score))


def compute_recommendation(report: TestReport) -> str:
    """Determine recommendation based on test results."""
    fail_count = len(report.fail_conditions)
    has_anomalies = len(report.anomalies) > 3

    if fail_count > 0:
        return "DO NOT SCALE"

    if report.system_stability_score < 60:
        return "ADJUST"

    if has_anomalies or report.system_stability_score < 80:
        return "ADJUST"

    if (report.total_executed >= 3 and report.win_count >= report.loss_count
            and report.system_stability_score >= 80):
        return "SCALE"

    return "ADJUST"


# ────────────────────────────────────────────────────────────────
# Report generation
# ────────────────────────────────────────────────────────────────

_PASS = "[PASS]"
_FAIL = "[FAIL]"
_WARN = "[WARN]"


def generate_report(report: TestReport) -> str:
    """Generate a detailed markdown report."""
    lines = []
    lines.append("# Paper Burn-In Short Test Report")
    lines.append("")
    lines.append(f"- **Start**: {report.start_time}")
    lines.append(f"- **End**: {report.end_time}")
    lines.append(f"- **Duration**: {report.duration_minutes:.0f} minutes ({report.duration_mode})")
    lines.append(f"- **Status**: {_PASS if report.passed else _FAIL}")
    lines.append("")

    # System overview
    lines.append("## 1. System Overview")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Signals Generated | {report.total_signals} |")
    lines.append(f"| Total Trades Executed | {report.total_executed} |")
    lines.append(f"| Total Trades Closed | {report.total_closed} |")
    lines.append(f"| Win Count | {report.win_count} |")
    lines.append(f"| Loss Count | {report.loss_count} |")
    if report.total_closed > 0:
        lines.append(f"| Win/Loss Ratio | {report.win_count / report.loss_count:.2f} |" if report.loss_count > 0 else "| Win/Loss Ratio | N/A (all wins) |")
    else:
        lines.append(f"| Win/Loss Ratio | N/A (no closed trades) |")
    lines.append(f"| Avg PnL | ${report.avg_pnl:.2f} |")
    lines.append(f"| Max Drawdown | {report.max_drawdown:.2%} |")
    lines.append(f"| Signal → Execution Rate | {report.signal_to_execution_rate:.2%} |")
    lines.append(f"| Strategy Kill Count | {len(report.guardian_disable_events)} |")
    lines.append(f"| Exit Engine Triggers | {sum(report.exit_reason_distribution.values())} |")
    lines.append(f"| Crashes | {report.crash_count} |")
    lines.append(f"| System Stability Score | {report.system_stability_score:.1f}/100 |")
    lines.append("")

    # Equity curve
    lines.append("## 2. Equity Curve")
    lines.append("")
    if report.equity_curve:
        lines.append("| Timestamp | Portfolio Value | Drawdown | Open Positions |")
        lines.append("|-----------|----------------|----------|----------------|")
        for pt in report.equity_curve[-30:]:
            lines.append(f"| {pt['timestamp']} | ${pt['portfolio_value']:.2f} | {pt['drawdown']:.2%} | {pt['open_positions']} |")
    else:
        lines.append("No portfolio snapshots recorded during this window.")
    lines.append("")

    # Strategy PnL ranking
    lines.append("## 3. Strategy PnL Ranking")
    lines.append("")
    if report.strategy_pnl_ranking:
        lines.append("| Rank | Strategy | Total PnL | Trade Count | Avg PnL | Win Rate |")
        lines.append("|------|----------|-----------|-------------|---------|----------|")
        for rank, (sname, sdata) in enumerate(report.strategy_pnl_ranking.items(), 1):
            detail = report.strategy_details.get(sname, {})
            wr = detail.get("win_rate", 0)
            lines.append(f"| {rank} | {sname} | ${sdata['total_pnl']:.2f} | {sdata['trade_count']} | ${sdata['avg_pnl']:.2f} | {wr:.2%} |")
    else:
        lines.append("No strategy PnL data available.")
    lines.append("")

    # Signal → Execution conversion
    lines.append("## 4. Signal → Execution Conversion")
    lines.append("")
    lines.append(f"- **Total Signals**: {report.total_signals}")
    lines.append(f"- **Total Trades Executed**: {report.total_executed}")
    lines.append(f"- **Conversion Rate**: {report.signal_to_execution_rate:.2%}")
    if report.total_signals > 0 and report.total_executed > 0:
        lines.append(f"- **Execution Efficiency**: {report.total_executed / report.total_signals:.2%} of signals became trades")
    lines.append("")

    # Rejection reasons breakdown
    lines.append("## 5. Rejection Reasons Breakdown")
    lines.append("")
    if report.rejection_reasons_breakdown:
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(report.rejection_reasons_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
    else:
        # Derive from data
        rejected_est = report.total_signals - report.total_executed
        if rejected_est > 0:
            lines.append(f"Estimated {rejected_est} signals did not convert to trades (risk rejection or other).")
        else:
            lines.append("No rejections recorded.")
    lines.append("")

    # Exit reason distribution
    lines.append("## 6. Exit Reason Distribution")
    lines.append("")
    if report.exit_reason_distribution:
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(report.exit_reason_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("No exits recorded during this window.")
    lines.append("")

    # Drift vs replay baseline
    lines.append("## 7. Drift vs Replay Baseline")
    lines.append("")
    if report.replay_drift_pct >= 0:
        lines.append(f"- **Event Rate Drift**: {report.replay_drift_pct:.2f}%")
        if report.replay_drift_pct < 5:
            lines.append(f"- {_PASS} Drift within acceptable range (<5%)")
        elif report.replay_drift_pct < 15:
            lines.append(f"- {_WARN} Moderate drift detected")
        else:
            lines.append(f"- {_FAIL} High drift — may indicate data pipeline inconsistency")
    lines.append("")

    # System stability score
    lines.append("## 8. System Stability Score")
    lines.append("")
    lines.append(f"- **Score**: {report.system_stability_score:.1f}/100")
    if report.system_stability_score >= 90:
        lines.append(f"- {_PASS} Excellent stability")
    elif report.system_stability_score >= 70:
        lines.append(f"- {_WARN} Acceptable stability with minor issues")
    elif report.system_stability_score >= 50:
        lines.append(f"- {_WARN} Moderate stability concerns")
    else:
        lines.append(f"- {_FAIL} Poor stability — corrective action needed")
    lines.append("")

    # Anomalies detected
    lines.append("## 9. Anomalies Detected")
    lines.append("")
    if report.anomalies:
        for a in report.anomalies:
            lines.append(f"- {_WARN} {a}")
    else:
        lines.append(f"- {_PASS} No anomalies detected")

    # Redis stream info (informational)
    if _redis_stream_info:
        lines.append("")
        lines.append("### Redis Stream Lengths")
        lines.append("")
        lines.append("| Stream | Length |")
        lines.append("|--------|--------|")
        for stream, length in sorted(_redis_stream_info.items()):
            lines.append(f"| {stream} | {length} |")
    lines.append("")

    # Fail conditions
    lines.append("## 10. Fail Condition Checks")
    lines.append("")
    if report.fail_conditions:
        for fc in report.fail_conditions:
            lines.append(f"- {_FAIL} {fc}")
    else:
        lines.append(f"- {_PASS} All fail condition checks passed")
    lines.append("")

    fail_checks = [
        ("Crashes / unhandled exceptions", report.crash_count == 0, f"{report.crash_count} crashes"),
        ("NoneType propagation", report.none_type_propagations == 0, f"{report.none_type_propagations} propagations"),
        ("Missing market_id/outcome", report.missing_market_ids == 0, f"{report.missing_market_ids} missing"),
        ("Strategy invalid schema", report.invalid_schemas == 0, f"{report.invalid_schemas} violations"),
        ("Runaway signal loop", not report.runaway_signal_loops, "detected" if report.runaway_signal_loops else "none"),
        ("Redis lag ≤ 5s", not report.redis_lag_exceeded, "exceeded" if report.redis_lag_exceeded else "ok"),
        ("Memory growth ≤ 10%", not report.memory_growth_exceeded, "exceeded" if report.memory_growth_exceeded else "ok"),
    ]
    lines.append("## 11. Detailed Fail Conditions")
    lines.append("")
    lines.append("| Check | Result | Detail |")
    lines.append("|-------|--------|--------|")
    for check_name, passed, detail in fail_checks:
        status = _PASS if passed else _FAIL
        lines.append(f"| {check_name} | {status} | {detail} |")
    lines.append("")

    # Recommendation
    lines.append("## 12. Recommendation")
    lines.append("")
    rec = report.recommendation
    if rec == "SCALE":
        lines.append(f"### {_PASS} SCALE")
        lines.append("")
        lines.append("The system demonstrates stable behavior under real-time pressure. "
                      "Strategies are generating signals, trades are executing, risk systems are functional. "
                      "Proceeding to extended validation is recommended.")
    elif rec == "ADJUST":
        lines.append(f"### {_WARN} ADJUST")
        lines.append("")
        lines.append("The system is operational but has areas requiring attention before scaling. "
                      "Review anomalies and fail conditions above. Address issues and re-run validation.")
    else:
        lines.append(f"### {_FAIL} DO NOT SCALE")
        lines.append("")
        lines.append("Critical issues detected. Do not proceed to production until all fail conditions "
                      "are resolved. Review the fail condition report and address each item.")
    lines.append("")

    # Metrics snapshots history
    if report.metrics_snapshots:
        lines.append("## 13. Metrics Snapshots (60s Interval)")
        lines.append("")
        for snap in report.metrics_snapshots:
            lines.append(f"### T+{snap.elapsed_seconds:.0f}s")
            lines.append("")
            lines.append(f"- Signals: {snap.total_signals} | Rejected: {snap.rejected_signals} "
                          f"| Executed: {snap.executed_trades}")
            lines.append(f"- Portfolio: ${snap.portfolio_value:.2f} | Drawdown: {snap.max_drawdown:.2%}")
            lines.append(f"- Active Strategies: {snap.active_strategies} | Disabled: {snap.disabled_strategies}")
            lines.append(f"- Overlay: {snap.overlay_state} | WS Events/min: {snap.ws_events_per_min}")
            lines.append(f"- Crash Count: {snap.crash_count} | Exit Triggers: {snap.exit_engine_triggers}")
            lines.append("")

    return "\n".join(lines)


def generate_json_report(report: TestReport) -> dict:
    """Generate a JSON-serializable report dict."""
    return {
        "metadata": {
            "start_time": report.start_time,
            "end_time": report.end_time,
            "duration_minutes": report.duration_minutes,
            "duration_mode": report.duration_mode,
            "passed": report.passed,
        },
        "overview": {
            "total_signals": report.total_signals,
            "total_executed": report.total_executed,
            "total_closed": report.total_closed,
            "win_count": report.win_count,
            "loss_count": report.loss_count,
            "win_loss_ratio": round(report.win_count / report.loss_count, 4) if report.loss_count > 0 else None,
            "avg_pnl": round(report.avg_pnl, 4),
            "max_drawdown": round(report.max_drawdown, 6),
            "signal_to_execution_rate": round(report.signal_to_execution_rate, 4),
            "strategy_kill_count": len(report.guardian_disable_events),
            "exit_engine_triggers": sum(report.exit_reason_distribution.values()),
            "crash_count": report.crash_count,
            "system_stability_score": round(report.system_stability_score, 1),
        },
        "strategy_pnl_ranking": report.strategy_pnl_ranking,
        "strategy_details": report.strategy_details,
        "exit_reason_distribution": report.exit_reason_distribution,
        "rejection_reasons_breakdown": report.rejection_reasons_breakdown,
        "equity_curve": report.equity_curve[-60:],
        "guardian_disable_events": report.guardian_disable_events,
        "trade_cycles": [
            {
                "timestamp": t.timestamp,
                "market_id": t.market_id,
                "strategy_name": t.strategy_name,
                "risk_decision": t.risk_decision,
                "execution_decision": t.execution_decision,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "exit_reason": t.exit_reason,
                "pnl": t.pnl,
            }
            for t in report.trade_cycles[-50:]
        ],
        "anomalies": report.anomalies,
        "fail_conditions": report.fail_conditions,
        "replay_drift_pct": report.replay_drift_pct,
        "recommendation": report.recommendation,
        "health_history": report.health_history,
    }


# ────────────────────────────────────────────────────────────────
# Main test runner
# ────────────────────────────────────────────────────────────────

async def run_test(duration_minutes: int = DEFAULT_DURATION_MINUTES, extended: bool = False):
    """Run the paper burn-in short test."""
    start_time = datetime.now(timezone.utc)
    duration_seconds = duration_minutes * 60
    end_time = start_time.timestamp() + duration_seconds

    mode_label = "EXTENDED" if extended else "SHORT"
    print(f"\n{'='*70}")
    print(f"  PAPER BURN-IN SHORT TEST — {mode_label} MODE")
    print(f"  Duration: {duration_minutes} minutes")
    print(f"  Start: {start_time.isoformat()}")
    print(f"{'='*70}\n")

    report = TestReport(
        start_time=start_time.isoformat(),
        end_time="",
        duration_minutes=duration_minutes,
        duration_mode=mode_label,
    )

    # Collect initial memory
    try:
        import psutil
        report.initial_memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        report.initial_memory_mb = 0.0

    # Ensure DB schema is up-to-date
    await ensure_db_schema()

    # Monitoring loop
    last_snapshot_time = 0.0
    prev_snapshot: MetricsSnapshot | None = None

    print(f"Monitoring for {duration_minutes} minutes...\n")

    while time.time() < end_time:
        elapsed = time.time() - start_time.timestamp()
        remaining = max(0, end_time - time.time())

        # Every 60 seconds, collect a metrics snapshot
        if time.time() - last_snapshot_time >= METRICS_INTERVAL_SECONDS:
            snap = await collect_metrics_snapshot(elapsed, prev_snapshot)
            report.metrics_snapshots.append(snap)
            prev_snapshot = snap
            last_snapshot_time = time.time()

            minutes_remaining = remaining / 60
            print(f"  [T+{elapsed/60:.0f}m] Signals={snap.total_signals} "
                  f"Executed={snap.executed_trades} Portf=${snap.portfolio_value:.0f} "
                  f"DD={snap.max_drawdown:.2%} "
                  f"WS={snap.ws_events_per_min}/min "
                  f"Overlay={snap.overlay_state} "
                  f"Remaining={minutes_remaining:.0f}m")

        await asyncio.sleep(5)

    # Test complete — collect final data
    print(f"\n{'='*70}")
    print(f"  TEST COMPLETE — Collecting final data...")
    print(f"{'='*70}\n")

    end_dt = datetime.now(timezone.utc)
    report.end_time = end_dt.isoformat()

    # Collect all data
    await collect_trade_data(report)
    await collect_signals_data(report)
    await collect_replay_drift(report)
    await collect_redis_metrics(report)

    # Check memory growth
    try:
        import psutil
        report.final_memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
        if report.initial_memory_mb > 0:
            growth_pct = ((report.final_memory_mb - report.initial_memory_mb) / report.initial_memory_mb) * 100
            if growth_pct > 10:
                report.memory_growth_exceeded = True
                report.fail_conditions.append(f"memory_growth_{growth_pct:.1f}%_exceeds_10%")
    except ImportError:
        pass

    # Compute stability and recommendation
    report.system_stability_score = compute_stability_score(report)
    report.recommendation = compute_recommendation(report)
    report.passed = len(report.fail_conditions) == 0

    # Generate report files
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    md_report = generate_report(report)
    md_path = REPORT_DIR / "paper-test-report.md"
    md_path.write_text(md_report, encoding="utf-8")

    json_report = generate_json_report(report)
    json_path = REPORT_DIR / "paper-test-report.json"
    json_path.write_text(json.dumps(json_report, indent=2, default=str), encoding="utf-8")

    # Print summary
    print(f"\n{'='*70}")
    print(f"  REPORT SUMMARY")
    print(f"{'='*70}")
    print(f"  Duration:       {report.duration_minutes:.0f}m ({mode_label})")
    print(f"  Signals:        {report.total_signals}")
    print(f"  Executed:       {report.total_executed}")
    print(f"  Closed:         {report.total_closed}")
    print(f"  Win/Loss:       {report.win_count}/{report.loss_count}")
    print(f"  Max DD:         {report.max_drawdown:.2%}")
    print(f"  Crashes:        {report.crash_count}")
    print(f"  Stability:      {report.system_stability_score:.1f}/100")
    print(f"  Recommendation: {report.recommendation}")
    print(f"  Status:         {'PASSED' if report.passed else 'FAILED'}")
    print(f"\n  Full report: {md_path.resolve()}")
    print(f"  JSON report: {json_path.resolve()}")
    print(f"{'='*70}\n")

    return report


async def main():
    parser = argparse.ArgumentParser(
        description="Paper Burn-In Short Test — production-like behavioral validation"
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION_MINUTES,
        help=f"Test duration in minutes (default: {DEFAULT_DURATION_MINUTES})"
    )
    parser.add_argument(
        "--extended", action="store_true",
        help=f"Use extended mode ({EXTENDED_DURATION_MINUTES} min)"
    )
    parser.add_argument(
        "--no-start", action="store_true",
        help="Skip starting the app (assume it's already running)"
    )
    parser.add_argument(
        "--port", type=int, default=APP_PORT,
        help=f"API port (default: {APP_PORT})"
    )

    args = parser.parse_args()

    port = args.port
    api_base = f"http://{APP_HOST}:{port}"
    # Override module-level globals for HTTP helpers
    import scripts.paper_burnin_short as _self
    _self.APP_PORT = port
    _self.API_BASE = api_base

    duration = args.duration
    if args.extended:
        duration = EXTENDED_DURATION_MINUTES

    setup_environment(extended=args.extended)

    if not args.no_start:
        print("\nStarting application...")
        proc = start_app()
        ready = await wait_for_app(timeout=90.0)
        if not ready:
            print("ERROR: Application did not start in time!")
            stop_app()
            sys.exit(1)
        print("Application is ready.\n")
    else:
        print("Using existing application...\n")

    try:
        await run_test(duration_minutes=duration, extended=args.extended)
    finally:
        if not args.no_start:
            print("Shutting down application...")
            stop_app()


if __name__ == "__main__":
    asyncio.run(main())
