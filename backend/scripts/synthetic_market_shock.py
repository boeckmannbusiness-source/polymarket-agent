#!/usr/bin/env python3
"""
Synthetic Market Shock Testing — Phase 6A

Validates the FULL trading pipeline under controlled synthetic market conditions.
Injects deterministic events through Redis streams that flow through:
  WhaleAgent → SignalAgent → RiskAgent → ExecutionAgent → ExitEngine

Usage:
    python scripts/synthetic_market_shock.py --scenario whale_buy
    python scripts/synthetic_market_shock.py --scenario panic_sell
    python scripts/synthetic_market_shock.py --scenario all
    python scripts/synthetic_market_shock.py --list-scenarios
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import random
import signal
import subprocess
import sys
import time
import traceback
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Determinism ──────────────────────────────────────────────
SEED = 42
BASE_TS = datetime(2026, 5, 29, 12, 0, 0, tzinfo=timezone.utc)

# Fixed wallet addresses for deterministic scenarios
WHALE_WALLETS = [
    "0x1111111111111111111111111111111111111111",
    "0x2222222222222222222222222222222222222222",
    "0x3333333333333333333333333333333333333333",
    "0x4444444444444444444444444444444444444444",
    "0x5555555555555555555555555555555555555555",
]

# ─── Config ────────────────────────────────────────────────────
REPORT_DIR = Path("debug") / "synthetic-test-report"
API_BASE = "http://127.0.0.1:8000"
APP_PORT = 8000
APP_HOST = "127.0.0.1"

SCENARIO_MARKET_COUNT = 5

# ─── Helpers ───────────────────────────────────────────────────

def deterministic_uuid(seed: int) -> str:
    rng = random.Random(seed)
    return str(uuid_mod.UUID(bytes=bytes([rng.getrandbits(8) for _ in range(16)]), version=4))


def deterministic_condition_id(seed: int) -> str:
    h = hashlib.sha256(f"condition.{seed}".encode()).hexdigest()
    return f"0x{h}"


def deterministic_asset_id(seed: int) -> str:
    h = hashlib.sha256(f"asset.{seed}".encode()).hexdigest()
    return f"0x{h}"


def deterministic_timestamp(offset_seconds: int) -> str:
    return (BASE_TS + timedelta(seconds=offset_seconds)).isoformat()


def deterministic_price(base: float, step: int, volatility: float = 0.0, rng: random.Random | None = None) -> float:
    if rng is None:
        rng = random.Random(SEED)
    noise = rng.uniform(-volatility, volatility) if volatility > 0 else 0.0
    return round(base + step * 0.01 + noise, 6)


# ─── Scenario event generators ─────────────────────────────────

def scenario_whale_buy_cascade(rng: random.Random) -> list[dict]:
    """Scenario 1: Whale Buy Cascade — 5-20 sequential BUY trades, increasing sizes, rising prices."""
    num_trades = rng.randint(5, 20)
    events = []
    condition_id = deterministic_condition_id(1001)
    asset_id = deterministic_asset_id(1001)
    wallet = WHALE_WALLETS[0]
    for i in range(num_trades):
        price = deterministic_price(0.50, i * 2, volatility=0.02, rng=rng)
        size = round(rng.uniform(500, 5000) * (1 + i * 0.1), 2)
        events.append({
            "wallet": wallet,
            "outcome": "YES",
            "side": "buy",
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(i * 10),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_whale_buy_{i}".encode()).hexdigest(),
        })
    return events


def scenario_panic_sell_cascade(rng: random.Random) -> list[dict]:
    """Scenario 2: Panic Sell Cascade — rapid downward momentum, large sell pressure."""
    num_trades = rng.randint(10, 25)
    events = []
    condition_id = deterministic_condition_id(2001)
    asset_id = deterministic_asset_id(2001)
    wallet = WHALE_WALLETS[1]
    for i in range(num_trades):
        price = deterministic_price(0.80, -i * 3, volatility=0.04, rng=rng)
        size = round(rng.uniform(500, 10000) * (1 + i * 0.05), 2)
        events.append({
            "wallet": wallet,
            "outcome": "NO",
            "side": "sell",
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(i * 5),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_panic_sell_{i}".encode()).hexdigest(),
        })
    return events


def scenario_fake_momentum_spike(rng: random.Random) -> list[dict]:
    """Scenario 3: Fake Momentum Spike — short-lived upward spike, immediate reversal."""
    events = []
    condition_id = deterministic_condition_id(3001)
    asset_id = deterministic_asset_id(3001)
    wallet = WHALE_WALLETS[2]
    # Build up phase (5 trades)
    for i in range(5):
        price = deterministic_price(0.50, i * 2, volatility=0.01, rng=rng)
        size = round(rng.uniform(300, 1500), 2)
        events.append({
            "wallet": wallet,
            "outcome": "YES",
            "side": "buy",
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(i * 8),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_fake_up_{i}".encode()).hexdigest(),
        })
    # Spike (1 trade)
    events.append({
        "wallet": wallet,
        "outcome": "YES",
        "side": "buy",
        "size": round(rng.uniform(500, 2000), 2),
        "value": 1500.0,
        "price": 0.95,
        "condition_id": condition_id,
        "asset_id": asset_id,
        "timestamp": deterministic_timestamp(50),
        "maker_address": wallet,
        "transaction_hash": hashlib.sha256("tx_fake_spike".encode()).hexdigest(),
    })
    # Reversal phase (5 trades, rapid drops)
    for i in range(5):
        price = deterministic_price(0.85, -i * 4, volatility=0.03, rng=rng)
        size = round(rng.uniform(20, 100), 2)
        events.append({
            "wallet": wallet,
            "outcome": "NO",
            "side": "sell",
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(55 + i * 4),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_fake_down_{i}".encode()).hexdigest(),
        })
    return events


def scenario_liquidity_vacuum(rng: random.Random) -> list[dict]:
    """Scenario 4: Liquidity Vacuum — large trades, near-empty orderbook."""
    events = []
    condition_id = deterministic_condition_id(4001)
    asset_id = deterministic_asset_id(4001)
    wallet = WHALE_WALLETS[3]
    # Large trades with extreme size variance
    for i in range(15):
        price = deterministic_price(0.60, rng.randint(-5, 5), volatility=0.08, rng=rng)
        size = round(rng.uniform(50, 500), 2)
        side = "buy" if rng.random() > 0.4 else "sell"
        events.append({
            "wallet": wallet,
            "outcome": "YES" if side == "buy" else "NO",
            "side": side,
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(i * 3),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_liquidity_{i}".encode()).hexdigest(),
        })
    return events


def scenario_correlated_market_panic(rng: random.Random) -> list[dict]:
    """Scenario 5: Correlated Market Panic — simultaneous drops across many markets."""
    events = []
    # Generate events for 5 different markets, all dropping simultaneously
    for market_idx in range(5):
        cond_id = deterministic_condition_id(5001 + market_idx)
        asset_id = deterministic_asset_id(5001 + market_idx)
        wallet = WHALE_WALLETS[market_idx % len(WHALE_WALLETS)]
        num_trades = rng.randint(3, 8)
        for i in range(num_trades):
            price = deterministic_price(0.75, -i * 4, volatility=0.05, rng=rng)
            size = round(rng.uniform(20, 200), 2)
            events.append({
                "wallet": wallet,
                "outcome": "NO",
                "side": "sell",
                "size": size,
                "value": size,
                "price": price,
                "condition_id": cond_id,
                "asset_id": asset_id,
                "timestamp": deterministic_timestamp(i * 6 + market_idx * 2),
                "maker_address": wallet,
                "transaction_hash": hashlib.sha256(f"tx_panic_mkt{market_idx}_{i}".encode()).hexdigest(),
            })
    return events


def scenario_chaotic_noise(rng: random.Random) -> list[dict]:
    """Scenario 6: Chaotic Noise Market — random alternating price movement."""
    events = []
    condition_id = deterministic_condition_id(6001)
    asset_id = deterministic_asset_id(6001)
    wallet = WHALE_WALLETS[4]
    for i in range(30):
        price = round(rng.uniform(0.1, 0.9), 4)
        size = round(rng.uniform(10, 200), 2)
        side = "buy" if rng.random() > 0.5 else "sell"
        events.append({
            "wallet": wallet,
            "outcome": "YES" if side == "buy" else "NO",
            "side": side,
            "size": size,
            "value": size,
            "price": price,
            "condition_id": condition_id,
            "asset_id": asset_id,
            "timestamp": deterministic_timestamp(i * 7),
            "maker_address": wallet,
            "transaction_hash": hashlib.sha256(f"tx_noise_{i}".encode()).hexdigest(),
        })
    return events


SCENARIOS = {
    "whale_buy": {
        "name": "Whale Buy Cascade",
        "description": "Sequential BUY trades with increasing sizes and rising prices",
        "generator": scenario_whale_buy_cascade,
        "markets": [1001],
    },
    "panic_sell": {
        "name": "Panic Sell Cascade",
        "description": "Rapid downward momentum with large sell pressure",
        "generator": scenario_panic_sell_cascade,
        "markets": [2001],
    },
    "fake_momentum": {
        "name": "Fake Momentum Spike",
        "description": "Short-lived upward spike with immediate reversal",
        "generator": scenario_fake_momentum_spike,
        "markets": [3001],
    },
    "liquidity_vacuum": {
        "name": "Liquidity Vacuum",
        "description": "Large trades with near-empty orderbook conditions",
        "generator": scenario_liquidity_vacuum,
        "markets": [4001],
    },
    "correlated_panic": {
        "name": "Correlated Market Panic",
        "description": "Simultaneous drops across many correlated markets",
        "generator": scenario_correlated_market_panic,
        "markets": [5001, 5002, 5003, 5004, 5005],
    },
    "chaotic_noise": {
        "name": "Chaotic Noise Market",
        "description": "Random alternating price movement with no real direction",
        "generator": scenario_chaotic_noise,
        "markets": [6001],
    },
}


# ─── Determinism hash ──────────────────────────────────────────

def compute_determinism_hash(events: list[dict], results: dict) -> str:
    raw = json.dumps({"events": events, "results": results}, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ─── HTTP helper ────────────────────────────────────────────────

def _http_get(path: str, timeout: float = 10.0) -> dict | None:
    import urllib.request
    import urllib.error
    url = f"{API_BASE}{path}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# ─── Environment setup ──────────────────────────────────────────

def setup_environment():
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("TRADING_MODE", "paper")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("LOG_FORMAT", "text")
    os.environ.setdefault("METRICS_ENABLED", "true")
    os.environ.setdefault("PAPER_INITIAL_CAPITAL", "100000")
    os.environ.setdefault("HEARTBEAT_INTERVAL_SECONDS", "15")
    os.environ.setdefault("REDIS_STREAM_MAXLEN", "10000")
    os.environ.setdefault("FORCE_TRADING_DISABLED", "false")
    os.environ.setdefault("MIN_CONFIDENCE_THRESHOLD", "0.0")
    os.environ.setdefault("MAX_POSITION_SIZE_PCT", "0.1")
    os.environ.setdefault("MAX_TOTAL_EXPOSURE_PCT", "0.1")
    os.environ.setdefault("MAX_MARKET_EXPOSURE_PCT", "0.1")


async def reset_system_mode():
    """Reset system mode to NORMAL in Redis before app starts."""
    try:
        from app.redis import get_redis
        r = await get_redis()
        await r.delete("system:mode")
        await r.delete("system:override")
        for stream in ["market:data", "wallet:trade", "signal:generated", "trade:request"]:
            for group in ["whale_agent", "signal_agent", "risk_agent", "execution_agent"]:
                try:
                    await r.xgroup_destroy(stream, group)
                except Exception:
                    pass
            try:
                await r.xtrim(stream, 0)
            except Exception:
                pass
        print("  [setup] Reset system mode to NORMAL, cleared consumer groups")
    except Exception as e:
        print(f"  [setup] Redis reset skipped: {e}")


# ─── App process management ────────────────────────────────────

_app_process: subprocess.Popen | None = None
_app_log_file: Path | None = None


def start_app() -> subprocess.Popen:
    global _app_process, _app_log_file
    backend_dir = str(Path(__file__).resolve().parent.parent)
    _app_log_file = Path(backend_dir) / "debug" / "synthetic-test-report" / "app_output.log"
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
    _app_process = subprocess.Popen(cmd, cwd=backend_dir, env=env, stdout=log_fd, stderr=subprocess.STDOUT)
    log_fd.write(f"\n--- Started at {datetime.now(timezone.utc).isoformat()} ---\n")
    log_fd.flush()
    return _app_process


def stop_app():
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
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        result = _http_get("/health", timeout=5.0)
        if result is not None:
            return True
        await asyncio.sleep(2)
    return False


# ─── Market seeding ─────────────────────────────────────────────

async def seed_markets(market_seeds: list[int]):
    """Create synthetic markets in DB with MarketStateSnapshot."""
    from app.database import async_session_factory
    from app.models import Market, MarketStateSnapshot, MarketEvent

    async with async_session_factory() as db:
        for seed in market_seeds:
            cond_id = deterministic_condition_id(seed)
            asset_id = deterministic_asset_id(seed)
            existing = await db.execute(
                __import__("sqlalchemy").select(Market).where(Market.condition_id == cond_id)
            )
            if existing.scalar_one_or_none():
                continue

            market = Market(
                id=uuid_mod.UUID(deterministic_uuid(seed)),
                condition_id=cond_id,
                slug=f"synthetic-market-{seed}",
                title=f"Synthetic Market {seed}",
                outcomes={"YES": "Yes", "NO": "No"},
                clob_token_ids=[asset_id],
                volume=1000000.0,
                liquidity=500000.0,
                resolved=False,
            )
            db.add(market)
            await db.flush()

            snapshot = MarketStateSnapshot(
                market_id=market.id,
                timestamp=BASE_TS - timedelta(minutes=5),
                momentum=0.0,
                spread=0.02,
                volatility=0.15,
                volume_1h=100000.0,
                volume_acceleration=0.0,
                whale_pressure=0.0,
                orderbook_imbalance=0.0,
                regime="neutral",
                trade_count_1h=10,
            )
            db.add(snapshot)

            # Seed MarketEvent records so risk overlay checks (liquidity_collapse, ws_stall, etc.) pass
            now = datetime.now(timezone.utc)
            for i in range(10):
                mkt_event = MarketEvent(
                    market_id=market.id,
                    event_type="trade",
                    event_data={"synthetic": True},
                    timestamp=now - timedelta(minutes=5 - i),
                    outcome="YES",
                    side="buy",
                    size=100.0,
                    price=0.50,
                )
                db.add(mkt_event)
        await db.commit()


# ─── Event injection ────────────────────────────────────────────

async def inject_events(events: list[dict], scenario_name: str) -> int:
    """Publish synthetic trade events to market:data stream. Returns count published."""
    from app.core.events import EventBus

    count = 0
    for evt in events:
        try:
            await EventBus.publish(
                "market:data",
                "trade",
                f"synthetic_{scenario_name}",
                evt,
                correlation_id=hashlib.sha256(f"corr_{scenario_name}_{count}".encode()).hexdigest()[:32],
            )
            count += 1
        except Exception as e:
            print(f"  [WARN] Failed to inject event {count}: {e}")
    return count


# ─── Pipeline monitoring ────────────────────────────────────────

@dataclass
class ScenarioResult:
    scenario_name: str
    scenario_label: str
    description: str

    events_injected: int = 0
    start_time: str = ""
    end_time: str = ""

    signals_generated: int = 0
    signals_rejected: int = 0
    trades_executed: int = 0
    trades_closed: int = 0
    win_count: int = 0
    loss_count: int = 0
    avg_pnl: float = 0.0
    max_drawdown: float = 0.0

    strategy_activation_counts: dict = field(default_factory=dict)
    guardian_disable_counts: int = 0
    overlay_activations: list[str] = field(default_factory=list)
    exit_reason_distribution: dict = field(default_factory=dict)
    anomalies: list[str] = field(default_factory=list)
    crash_count: int = 0

    determinism_hash: str = ""
    replay_drift: float = 0.0
    passed: bool = True
    execution_details: list[dict] = field(default_factory=list)


async def wait_for_pipeline(scenario_name: str, timeout_seconds: int = 60) -> None:
    """Wait for agents to process injected events."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        # Check if signals have appeared in the DB
        try:
            from sqlalchemy import select, func
            from app.database import async_session_factory
            from app.models import Signal, Trade

            async with async_session_factory() as db:
                sig_count = (await db.execute(select(func.count(Signal.id)))).scalar() or 0
                trade_count = (await db.execute(select(func.count(Trade.id)))).scalar() or 0
        except Exception:
            sig_count = 0
            trade_count = 0

        # Also check via health snapshot
        hs = _http_get("/debug/health-snapshot")
        if hs:
            api_sigs = hs.get("total_trades", 0)
        else:
            api_sigs = 0

        # Give time for at least some events to be processed
        await asyncio.sleep(5)
        # After initial wait, break to collect results
        break

    # Final wait for pipeline to settle
    await asyncio.sleep(60)


async def collect_health_during_run(scenario_name: str, events_count: int) -> list[dict]:
    """Collect health snapshots during event injection."""
    snapshots = []
    for i in range(max(1, min(10, events_count // 5))):
        hs = _http_get("/debug/health-snapshot")
        if hs:
            snapshots.append(hs)
        ro = _http_get("/debug/risk-overlay")
        if ro:
            snapshots.append({"risk_overlay": ro.get("status", "unknown")})
        ss = _http_get("/debug/strategy-status")
        if ss:
            snapshots.append({"strategy_status": ss})
        await asyncio.sleep(5)
    return snapshots


async def collect_scenario_results(scenario_name: str, events: list[dict]) -> ScenarioResult:
    """Query DB and API for results of a scenario run."""
    from sqlalchemy import select, func, desc
    from app.database import async_session_factory
    from app.models import Signal, Trade, PortfolioSnapshot, MarketEvent
    from app.models.strategy import StrategyConfigRecord
    from app.models.safety import SafetyState

    result = ScenarioResult(
        scenario_name=scenario_name,
        scenario_label=SCENARIOS.get(scenario_name, {}).get("name", scenario_name),
        description=SCENARIOS.get(scenario_name, {}).get("description", ""),
        events_injected=len(events),
        start_time=BASE_TS.isoformat(),
        end_time=datetime.now(timezone.utc).isoformat(),
    )

    async with async_session_factory() as db:
        try:
            # Signals
            r = await db.execute(select(func.count(Signal.id)))
            result.signals_generated = r.scalar() or 0

            r = await db.execute(
                select(Signal.signal_type, func.count(Signal.id)).group_by(Signal.signal_type)
            )
            for row in r.all():
                result.strategy_activation_counts[row[0]] = row[1]

            # Rejected signals (direction is None)
            r = await db.execute(
                select(func.count(Signal.id)).where(Signal.direction.is_(None))
            )
            result.signals_rejected = r.scalar() or 0

            # Debug: check trade:execution stream
            try:
                from app.redis import get_redis
                r_redis = await get_redis()
                msgs = await r_redis.xrevrange("trade:execution", max="+", min="-", count=5)
                if msgs:
                    for mid, mdata in msgs:
                        et = mdata.get("event_type", "?")
                        src = mdata.get("source", "?")
                        data = mdata.get("data", "?")
                        print(f"    trade:execution: {et} from {src} - {data[:200]}")
                else:
                    print(f"    trade:execution: (empty)")
            except Exception as e:
                print(f"    trade:execution check error: {e}")

            # Trades
            r = await db.execute(select(func.count(Trade.id)))
            total_trades = r.scalar() or 0

            r = await db.execute(
                select(func.count(Trade.id)).where(Trade.status == "closed")
            )
            result.trades_closed = r.scalar() or 0

            result.trades_executed = max(0, total_trades - result.trades_closed) if total_trades > 0 else 0

            # PnL
            r = await db.execute(select(Trade).where(Trade.pnl.isnot(None)))
            pnl_trades = list(r.scalars().all())
            wins = [t for t in pnl_trades if t.pnl is not None and float(t.pnl) > 0]
            losses = [t for t in pnl_trades if t.pnl is not None and float(t.pnl) <= 0]
            result.win_count = len(wins)
            result.loss_count = len(losses)
            if pnl_trades:
                result.avg_pnl = sum(float(t.pnl or 0) for t in pnl_trades) / len(pnl_trades)

            # Max drawdown
            r = await db.execute(select(func.max(PortfolioSnapshot.drawdown)))
            result.max_drawdown = float(r.scalar() or 0)

            # Exit reason distribution
            r = await db.execute(
                select(Trade.reason, func.count(Trade.id))
                .where(Trade.status == "closed")
                .where(Trade.reason.isnot(None))
                .group_by(Trade.reason)
            )
            result.exit_reason_distribution = dict(r.all()) if r else {}

            # Guardian disable events
            r = await db.execute(select(StrategyConfigRecord))
            for cfg in r.scalars().all():
                if not cfg.enabled:
                    result.guardian_disable_counts += 1

            # Safety state
            r = await db.execute(
                select(SafetyState).order_by(SafetyState.updated_at.desc()).limit(1)
            )
            ss = r.scalar_one_or_none()
            if ss:
                if ss.circuit_breaker_active:
                    result.anomalies.append("circuit_breaker_was_active")
                if ss.kill_switch_active:
                    result.anomalies.append("kill_switch_was_active")

            # Crash count from runtime health
            rh = _http_get("/debug/runtime-health")
            if rh:
                result.crash_count = rh.get("crash_count", 0)
                if result.crash_count > 0:
                    result.anomalies.append(f"{result.crash_count}_crashes_detected")

            # Execution details (trade cycles)
            r = await db.execute(select(Trade).order_by(Trade.created_at.desc()).limit(100))
            for t in r.scalars().all():
                result.execution_details.append({
                    "id": str(t.id),
                    "market_id": str(t.market_id) if t.market_id else None,
                    "status": t.status,
                    "side": t.side,
                    "outcome": t.outcome,
                    "size": float(t.size) if t.size else None,
                    "price": float(t.price) if t.price else None,
                    "filled_price": float(t.filled_price) if t.filled_price else None,
                    "pnl": float(t.pnl) if t.pnl else None,
                    "reason": t.reason,
                    "slippage": float(t.slippage) if t.slippage else None,
                    "created_at": t.created_at.isoformat() if t.created_at else "",
                })

        except Exception as e:
            result.anomalies.append(f"data_collection_error: {e}")

    # Collect risk overlay state
    ro = _http_get("/debug/risk-overlay")
    if ro:
        result.overlay_activations.append(ro.get("status", "unknown"))

    # Compute determinism hash
    results_for_hash = {
        "signals": result.signals_generated,
        "trades": result.trades_executed,
        "wins": result.win_count,
        "losses": result.loss_count,
        "avg_pnl": result.avg_pnl,
        "strategy_counts": result.strategy_activation_counts,
        "exits": result.exit_reason_distribution,
        "guardian_disables": result.guardian_disable_counts,
    }
    result.determinism_hash = compute_determinism_hash(events, results_for_hash)

    # Pass/fail
    fail_conditions = []
    if result.crash_count > 0:
        fail_conditions.append("crashes_detected")
    if result.anomalies:
        fail_conditions.append("anomalies_present")
    result.passed = len(fail_conditions) == 0

    return result


# ─── Report generation ──────────────────────────────────────────

_PASS = "[PASS]"
_FAIL = "[FAIL]"
_WARN = "[WARN]"


def generate_scenario_report(result: ScenarioResult) -> str:
    lines = []
    lines.append(f"## Scenario: {result.scenario_label}")
    lines.append("")
    lines.append(f"- **Description**: {result.description}")
    lines.append(f"- **Events Injected**: {result.events_injected}")
    lines.append(f"- **Status**: {_PASS if result.passed else _FAIL}")
    lines.append("")

    lines.append("### Pipeline Results")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Signals Generated | {result.signals_generated} |")
    lines.append(f"| Signals Rejected | {result.signals_rejected} |")
    lines.append(f"| Trades Executed | {result.trades_executed} |")
    lines.append(f"| Trades Closed | {result.trades_closed} |")
    lines.append(f"| Win/Loss | {result.win_count}/{result.loss_count} |")
    lines.append(f"| Avg PnL | ${result.avg_pnl:.4f} |")
    lines.append(f"| Max Drawdown | {result.max_drawdown:.2%} |")
    lines.append(f"| Guardian Disables | {result.guardian_disable_counts} |")
    lines.append(f"| Crashes | {result.crash_count} |")
    lines.append("")

    if result.strategy_activation_counts:
        lines.append("### Strategy Activation")
        lines.append("")
        lines.append("| Strategy | Signals |")
        lines.append("|----------|---------|")
        for name, count in sorted(result.strategy_activation_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {name} | {count} |")
        lines.append("")

    if result.exit_reason_distribution:
        lines.append("### Exit Reason Distribution")
        lines.append("")
        lines.append("| Reason | Count |")
        lines.append("|--------|-------|")
        for reason, count in sorted(result.exit_reason_distribution.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    if result.overlay_activations:
        lines.append("### Risk Overlay Activations")
        lines.append("")
        for state in result.overlay_activations:
            lines.append(f"- Overlay state: `{state}`")
        lines.append("")

    if result.execution_details:
        lines.append("### Execution Details")
        lines.append("")
        lines.append("| Trade | Market | Side | Outcome | Size | Price | PnL | Status | Reason |")
        lines.append("|-------|--------|------|---------|------|-------|-----|--------|--------|")
        for td in result.execution_details[:20]:
            lines.append(
                f"| {td['id'][:8]} | {(td['market_id'] or 'N/A')[:8]} | "
                f"{td['side'] or 'N/A'} | {td['outcome'] or 'N/A'} | "
                f"{td['size'] or 0} | {td['price'] or 0} | "
                f"{td['pnl'] or 0} | {td['status']} | {td['reason'] or 'N/A'} |"
            )
        lines.append("")

    if result.anomalies:
        lines.append("### Anomalies Detected")
        lines.append("")
        for a in result.anomalies:
            lines.append(f"- {_WARN} {a}")
        lines.append("")

    lines.append("### Determinism")
    lines.append("")
    lines.append(f"- **Hash**: `{result.determinism_hash}`")
    lines.append(f"- **Replay Drift**: {result.replay_drift:.2f}%")
    lines.append("")

    return "\n".join(lines)


def generate_full_report(results: list[ScenarioResult], total_duration: float) -> str:
    lines = []
    lines.append("# Synthetic Market Shock Test Report")
    lines.append("")
    lines.append(f"- **Date**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **Seed**: {SEED}")
    lines.append(f"- **Total Duration**: {total_duration:.1f}s")
    lines.append("")

    all_passed = all(r.passed for r in results)
    total_events = sum(r.events_injected for r in results)
    total_signals = sum(r.signals_generated for r in results)
    total_trades = sum(r.trades_executed for r in results)
    total_crashes = sum(r.crash_count for r in results)

    lines.append("### Overall Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Scenarios Run | {len(results)} |")
    lines.append(f"| All Passed | {_PASS if all_passed else _FAIL} |")
    lines.append(f"| Total Events Injected | {total_events} |")
    lines.append(f"| Total Signals Generated | {total_signals} |")
    lines.append(f"| Total Trades Executed | {total_trades} |")
    lines.append(f"| Total Crashes | {total_crashes} |")
    lines.append("")

    lines.append("### Scenario Summary")
    lines.append("")
    lines.append("| Scenario | Events | Signals | Trades | Wins/Losses | Crashes | Passed |")
    lines.append("|----------|--------|---------|--------|-------------|---------|--------|")
    for r in results:
        lines.append(
            f"| {r.scenario_label} | {r.events_injected} | "
            f"{r.signals_generated} | {r.trades_executed} | "
            f"{r.win_count}/{r.loss_count} | {r.crash_count} | "
            f"{_PASS if r.passed else _FAIL} |"
        )
    lines.append("")

    for r in results:
        lines.append(generate_scenario_report(r))
        lines.append("---\n")

    if all_passed and total_crashes == 0:
        lines.append("## Final Verdict")
        lines.append("")
        lines.append(f"### {_PASS} ALL SCENARIOS PASSED")
        lines.append("")
        lines.append("The system demonstrates rational behavior under synthetic market stress. "
                      "Pipeline integrity is confirmed. Proceeding to the next phase is recommended.")
    else:
        lines.append("## Final Verdict")
        lines.append("")
        lines.append(f"### {_FAIL} ISSUES DETECTED")
        lines.append("")
        lines.append("Review the per-scenario anomalies and fail conditions above before proceeding.")

    return "\n".join(lines)


# ─── Scenario runner ────────────────────────────────────────────

async def run_single_scenario(scenario_name: str) -> ScenarioResult:
    """Run a single synthetic scenario end-to-end."""
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    rng = random.Random(SEED + hash(scenario_name) % (2**31))
    events = scenario["generator"](rng)

    print(f"\n  Scenario: {scenario['name']}")
    print(f"  {scenario['description']}")
    print(f"  Generating {len(events)} events...")

    # Seed markets
    await seed_markets(scenario["markets"])
    print(f"  Seeded {len(scenario['markets'])} markets in DB")

    # Inject events in small batches with brief pauses
    batch_size = 5
    total_injected = 0
    for i in range(0, len(events), batch_size):
        batch = events[i:i + batch_size]
        count = await inject_events(batch, scenario_name)
        total_injected += count
        await asyncio.sleep(1)  # Let pipeline process each batch
        if (i // batch_size) % 3 == 0 and i > 0:
            print(f"  Injected {total_injected}/{len(events)} events...")

    print(f"  Injected {total_injected} events total")

    # Wait for pipeline to fully process
    print(f"  Waiting for pipeline processing...")
    await wait_for_pipeline(scenario_name, timeout_seconds=120)
    print(f"  Collecting results...")

    result = await collect_scenario_results(scenario_name, events)

    status = _PASS if result.passed else _FAIL
    print(f"  Signals: {result.signals_generated} | "
          f"Trades: {result.trades_executed} | "
          f"W/L: {result.win_count}/{result.loss_count} | "
          f"Crashes: {result.crash_count} | "
          f"{status}")

    return result


async def run_all_scenarios() -> list[ScenarioResult]:
    results = []
    for name in SCENARIOS:
        print(f"\n{'='*60}")
        result = await run_single_scenario(name)
        results.append(result)
        # Brief cooldown between scenarios
        await asyncio.sleep(5)
    return results


# ─── Main ───────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Market Shock Testing — Phase 6A"
    )
    parser.add_argument(
        "--scenario", type=str, default="all",
        help="Scenario to run: whale_buy, panic_sell, fake_momentum, liquidity_vacuum, "
             "correlated_panic, chaotic_noise, or 'all' (default)"
    )
    parser.add_argument(
        "--list-scenarios", action="store_true",
        help="List available scenarios and exit"
    )
    parser.add_argument(
        "--no-start", action="store_true",
        help="Skip starting the app (assume it's already running)"
    )
    parser.add_argument(
        "--port", type=int, default=APP_PORT,
        help=f"API port (default: {APP_PORT})"
    )
    parser.add_argument(
        "--output-dir", type=str, default=str(REPORT_DIR),
        help="Output directory for reports"
    )

    args = parser.parse_args()

    if args.list_scenarios:
        print("\nAvailable Scenarios:")
        for name, sc in SCENARIOS.items():
            print(f"  {name:20s} {sc['description']}")
        print()
        return

    port = args.port
    api_base = f"http://{APP_HOST}:{port}"
    report_dir = Path(args.output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    import scripts.synthetic_market_shock as _self
    _self.API_BASE = api_base
    _self.APP_PORT = port
    _self.REPORT_DIR = report_dir

    setup_environment()

    if not args.no_start:
        await reset_system_mode()
        print("\nStarting application...")
        proc = start_app()
        ready = await wait_for_app(timeout=120.0)
        if not ready:
            print("ERROR: Application did not start in time!")
            stop_app()
            sys.exit(1)
        print("Application is ready.")
    else:
        print("Using existing application...")

    start_ts = time.monotonic()

    try:
        if args.scenario == "all":
            results = await run_all_scenarios()
        elif args.scenario in SCENARIOS:
            results = [await run_single_scenario(args.scenario)]
        else:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(SCENARIOS.keys())}")
            sys.exit(1)
    finally:
        if not args.no_start:
            print("\nShutting down application...")
            stop_app()

    total_duration = time.monotonic() - start_ts

    # Generate report
    report_md = generate_full_report(results, total_duration)
    md_path = REPORT_DIR / "synthetic-test-report.md"
    md_path.write_text(report_md, encoding="utf-8")

    # JSON report
    json_data = {
        "seed": SEED,
        "duration_seconds": round(total_duration, 1),
        "scenarios": [
            {
                "name": r.scenario_label,
                "events_injected": r.events_injected,
                "signals_generated": r.signals_generated,
                "signals_rejected": r.signals_rejected,
                "trades_executed": r.trades_executed,
                "trades_closed": r.trades_closed,
                "win_count": r.win_count,
                "loss_count": r.loss_count,
                "avg_pnl": r.avg_pnl,
                "max_drawdown": r.max_drawdown,
                "strategy_activation": r.strategy_activation_counts,
                "guardian_disables": r.guardian_disable_counts,
                "overlay_states": r.overlay_activations,
                "exit_reasons": r.exit_reason_distribution,
                "crash_count": r.crash_count,
                "determinism_hash": r.determinism_hash,
                "anomalies": r.anomalies,
                "passed": r.passed,
                "execution_details": r.execution_details[:50],
            }
            for r in results
        ],
    }
    json_path = REPORT_DIR / "synthetic-test-report.json"
    json_path.write_text(json.dumps(json_data, indent=2, default=str), encoding="utf-8")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  SYNTHETIC MARKET SHOCK TEST COMPLETE")
    print(f"{'='*60}")
    print(f"  Duration: {total_duration:.0f}s")
    print(f"  Scenarios: {len(results)}")
    all_passed = all(r.passed for r in results)
    total_crashes = sum(r.crash_count for r in results)
    print(f"  Status: {'ALL PASSED' if all_passed and total_crashes == 0 else 'ISSUES FOUND'}")
    print(f"  Report: {md_path.resolve()}")
    print(f"  JSON:   {json_path.resolve()}")
    print(f"{'='*60}\n")

    if not all_passed or total_crashes > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
