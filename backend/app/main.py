import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging, logger
from app.database import init_db
from app.redis import close_redis
from app.ingesters.polymarket_rest import PolymarketRESTIngester
from app.ingesters.polymarket_ws import PolymarketWSIngester
from app.agents.orchestrator import Orchestrator
from app.services.event_bridge import EventPersistenceBridge


_ws_ingester: PolymarketWSIngester | None = None
_bridge: EventPersistenceBridge | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ws_ingester, _bridge
    setup_logging()
    logger.info("starting_up", env=settings.APP_ENV, mode=settings.TRADING_MODE)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    rest_ingester = PolymarketRESTIngester(poll_interval=60)
    _ws_ingester = PolymarketWSIngester()
    ws_ingester = _ws_ingester
    _bridge = EventPersistenceBridge()
    bridge = _bridge
    orchestrator = Orchestrator()

    bg_tasks = []

    bg_tasks.append(asyncio.create_task(rest_ingester.run(), name="rest_ingester"))
    logger.info("rest_ingester_started", interval=60)

    bg_tasks.append(asyncio.create_task(ws_ingester.run(), name="ws_ingester"))
    logger.info("ws_ingester_started")

    bg_tasks.append(asyncio.create_task(bridge.start(), name="event_bridge"))
    logger.info("event_bridge_started")

    bg_tasks.append(asyncio.create_task(orchestrator.start_all(), name="orchestrator"))
    logger.info("orchestrator_started")

    yield

    logger.info("shutting_down")
    await rest_ingester.stop()
    await ws_ingester.stop()
    await bridge.stop()
    await orchestrator.stop_all()
    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    await close_redis()
    logger.info("shutdown_complete")


app = FastAPI(
    title="Polymarket Intelligence Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "mode": settings.TRADING_MODE, "env": settings.APP_ENV}


@app.get("/system/status")
async def system_status():
    return {
        "app": {"env": settings.APP_ENV, "mode": settings.TRADING_MODE},
        "ingesters": {
            "rest": "started",
            "websocket": "started",
        },
        "orchestrator": "started",
        "services": {
            "event_bridge": "started",
        },
    }


@app.get("/debug/replay-check")
async def debug_replay_check():
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        engine = ReplayEngine(db, ExecutionSimulator())
        result = await engine.run(
            strategy_name="whale_following",
            start_time=now - timedelta(days=7),
            end_time=now,
            mode=ReplayMode.SIGNAL_ONLY,
            signal_interval_seconds=1,
        )
        samples = [
            {"strategy": s.strategy_name, "signal": s.signal.signal,
             "confidence": s.signal.confidence, "price": s.entry_price}
            for s in result.signals[:3]
        ]
        return {
            "events_found": result.total_events_processed,
            "signals_generated": result.signals_generated,
            "signals_count": len(result.signals),
            "sample_signals": samples,
        }


@app.get("/debug/replay-drift")
async def debug_replay_drift(strategy: str = "whale_following", hours: float = 4):
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from datetime import datetime, timezone, timedelta
    from app.models import MarketEvent
    from sqlalchemy import select, func
    import hashlib

    async with async_session_factory() as db:
        r = await db.execute(select(func.max(MarketEvent.timestamp)))
        latest_ts = r.scalar()
        if latest_ts is None:
            return {"pass": True, "error": "no events in DB"}
        end = latest_ts - timedelta(minutes=1)
        start = end - timedelta(hours=hours)

    drift_fields = ["strategy_name", "entry_timestamp", "entry_price",
                    "outcome_5m", "outcome_15m", "outcome_1h", "outcome_4h", "outcome_close",
                    "pnl_5m", "pnl_15m", "pnl_1h", "pnl_4h", "pnl_close",
                    "max_favorable_excursion", "max_adverse_excursion",
                    "execution_slippage", "execution_fill_price"]

    def _hash(signals):
        rows = [str([getattr(s, f, None) for f in drift_fields]) for s in signals]
        return hashlib.sha256("|".join(rows).encode()).hexdigest()

    async with async_session_factory() as db:
        engine1 = ReplayEngine(db, ExecutionSimulator())
        r1 = await engine1.run(strategy, start, end, ReplayMode.SIGNAL_ONLY, signal_interval_seconds=1)
        h1 = _hash(r1.signals)

        engine2 = ReplayEngine(db, ExecutionSimulator())
        r2 = await engine2.run(strategy, start, end, ReplayMode.SIGNAL_ONLY, signal_interval_seconds=1)
        h2 = _hash(r2.signals)

    return {
        "pass": h1 == h2,
        "hash_run1": h1,
        "hash_run2": h2,
        "signal_count": len(r1.signals),
        "events_processed": r1.total_events_processed,
    }


@app.get("/debug/backfill-events/{n_markets}/{n_per_market}")
async def backfill_events(n_markets: int = 3, n_per_market: int = 3):
    from app.database import async_session_factory
    from app.models import Market, MarketEvent
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    import random

    WHALES = [
        "0x" + "".join(random.choices("abcdef0123456789", k=40))
        for _ in range(20)
    ]

    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        result = await db.execute(select(Market))
        all_markets = list(result.scalars().all())
        markets = all_markets[:n_markets]
        count = 0
        for market in markets:
            vol = float(market.volume) if market.volume else 100_000
            for i in range(n_per_market):
                price = round(random.uniform(0.1, 0.9), 4)
                is_whale = i % 5 == 0
                size = random.uniform(600, 5000) if is_whale else random.uniform(10, 200)
                event = MarketEvent(
                    market_id=market.id, event_type="trade",
                    event_data={}, price=price, size=size,
                    maker_address=random.choice(WHALES) if is_whale else None,
                    taker_address=None,
                    outcome="YES" if price > 0.5 else "NO",
                    timestamp=now - timedelta(hours=random.randint(0, 168)),
                )
                db.add(event)
                count += 1
        await db.commit()
        return {"events_created": count, "markets_seeded": len(markets)}


@app.post("/debug/backfill-clob-ids")
async def debug_backfill_clob_ids():
    from app.database import async_session_factory
    from sqlalchemy import text

    async with async_session_factory() as db:
        result = await db.execute(text("""
            UPDATE markets
            SET clob_token_ids = string_to_array(clob_token_ids[1], '", "')
            WHERE clob_token_ids IS NOT NULL
            AND array_length(clob_token_ids, 1) = 1
            AND clob_token_ids[1] LIKE '%", "%'
            RETURNING condition_id
        """))
        fixed = len(result.all())
        await db.commit()
    return {"markets_fixed": fixed}


@app.get("/debug/db-counts")
async def db_counts():
    from app.database import async_session_factory
    from sqlalchemy import select, func
    from app.models import (
        Market, MarketEvent, Signal, Trade, Position,
        PortfolioSnapshot, SignalOutcome, MarketStateSnapshot,
        Wallet, WalletTrade, StrategyConfigRecord,
    )

    async with async_session_factory() as db:
        tables = {
            "markets": Market,
            "market_events": MarketEvent,
            "signals": Signal,
            "trades": Trade,
            "positions": Position,
            "portfolio_snapshots": PortfolioSnapshot,
            "signal_outcomes": SignalOutcome,
            "market_state_snapshots": MarketStateSnapshot,
            "wallets": Wallet,
            "wallet_trades": WalletTrade,
            "strategy_configs": StrategyConfigRecord,
        }
        counts = {}
        for name, model in tables.items():
            try:
                result = await db.execute(select(func.count()).select_from(model))
                counts[name] = result.scalar() or 0
            except Exception as e:
                counts[name] = str(e)
        return counts


@app.get("/debug/ws-status")
async def debug_ws_status():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    try:
        s = _ws_ingester.stats
        return s
    except Exception as e:
        import traceback
        return {"error": str(e), "ingester_initialized": True, "traceback": traceback.format_exc()}


@app.get("/debug/ws-mappings")
async def debug_ws_mappings():
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models import Market

    async with async_session_factory() as db:
        result = await db.execute(
            select(Market.condition_id, Market.clob_token_ids, Market.slug, Market.title, Market.resolved)
            .where(Market.clob_token_ids.isnot(None))
            .limit(200)
        )
        rows = result.all()
    mappings = []
    for condition_id, token_ids, slug, title, resolved in rows:
        ids = [t for t in (token_ids or []) if t]
        if not ids:
            continue
        for tid in ids:
            mappings.append({
                "asset_id": tid,
                "condition_id": condition_id,
                "slug": slug,
                "title": (title or "")[:60],
                "resolved": resolved,
            })
    mapped_assets = {m["asset_id"] for m in mappings}
    return {
        "total_mappings": len(mappings),
        "sample": mappings[:50],
        "unique_asset_ids": len(mapped_assets),
    }


@app.get("/debug/data-quality")
async def debug_data_quality():
    from app.database import async_session_factory
    from sqlalchemy import select, func
    from app.models import Market, MarketEvent
    from datetime import datetime, timezone, timedelta

    async with async_session_factory() as db:
        total_events = await db.execute(select(func.count()).select_from(MarketEvent))
        total_events = total_events.scalar() or 0

        total_markets = await db.execute(select(func.count()).select_from(Market))
        total_markets = total_markets.scalar() or 0

        resolved = await db.execute(
            select(func.count()).select_from(Market).where(Market.resolved == True)
        )
        resolved = resolved.scalar() or 0

        with_ids = await db.execute(
            select(func.count()).select_from(Market).where(Market.clob_token_ids.isnot(None))
        )
        with_ids = with_ids.scalar() or 0

        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        events_24h = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.timestamp >= cutoff)
        )
        events_24h = events_24h.scalar() or 0

        orphan_events = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.market_id.is_(None))
        )
        orphan_events = orphan_events.scalar() or 0

        return {
            "total_market_events": total_events,
            "total_markets": total_markets,
            "markets_with_clob_ids": with_ids,
            "resolved_markets": resolved,
            "events_last_24h": events_24h,
            "events_per_minute_24h": round(events_24h / 1440, 2) if events_24h else 0,
            "orphan_events": orphan_events,
            "mapping_coverage_pct": round(with_ids / total_markets * 100, 1) if total_markets else 0,
        }


@app.get("/debug/trade/{trade_id}")
async def debug_trade_forensics(trade_id: int):
    from app.database import async_session_factory
    from app.models import BacktestTrade, MarketEvent, Market
    from sqlalchemy import select
    from datetime import timedelta

    async with async_session_factory() as db:
        trade = await db.execute(select(BacktestTrade).where(BacktestTrade.id == trade_id))
        trade = trade.scalar_one_or_none()
        if not trade:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Trade not found")

        market = None
        raw_events = []
        if trade.market_id:
            market_row = await db.execute(select(Market).where(Market.id == trade.market_id))
            market = market_row.scalar_one_or_none()
            events = await db.execute(
                select(MarketEvent).where(MarketEvent.market_id == trade.market_id)
                .where(MarketEvent.timestamp.between(
                    trade.entry_timestamp - timedelta(hours=1),
                    (trade.exit_timestamp or trade.entry_timestamp) + timedelta(hours=1),
                ))
                .order_by(MarketEvent.timestamp)
                .limit(500)
            )
            raw_events = [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "price": float(e.price) if e.price else None,
                    "size": float(e.size) if e.size else None,
                    "maker": e.maker_address,
                    "outcome": e.outcome,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events.scalars().all()
            ]

        return {
            "trade": {
                "id": trade.id,
                "side": trade.side,
                "outcome": trade.outcome,
                "entry_price": float(trade.entry_price) if trade.entry_price else None,
                "exit_price": float(trade.exit_price) if trade.exit_price else None,
                "size": float(trade.size),
                "pnl": float(trade.pnl) if trade.pnl else None,
                "entry_timestamp": trade.entry_timestamp.isoformat() if trade.entry_timestamp else None,
                "exit_timestamp": trade.exit_timestamp.isoformat() if trade.exit_timestamp else None,
                "signal_type": trade.signal_type,
                "extra_data": trade.extra_data,
            },
            "market": {
                "id": str(market.id) if market else None,
                "condition_id": market.condition_id if market else None,
                "slug": market.slug if market else None,
                "title": market.title if market else None,
            } if market else None,
            "surrounding_events": raw_events[:100],
            "event_count": len(raw_events),
        }


@app.get("/debug/bridge-stats")
async def debug_bridge_stats():
    global _bridge
    if _bridge is None:
        return {"error": "bridge not initialized"}
    return _bridge.stats


@app.get("/debug/redis-stream")
async def debug_redis_stream():
    from app.redis import get_redis
    r = await get_redis()
    try:
        info = await r.xinfo_stream("market:data")
        return {"stream": "market:data", "info": info}
    except Exception as e:
        return {"stream": "market:data", "error": str(e)}


@app.post("/debug/backfill-real-trades")
async def debug_backfill_real_trades(
    days: int = Query(default=7, ge=1, le=30, description="Days of history to fetch"),
    limit_per_asset: int = Query(default=500, ge=1, le=1000, description="Max trades per asset"),
    concurrency: int = Query(default=20, ge=1, le=50, description="Concurrent API calls"),
):
    from app.database import async_session_factory
    from app.models import Market, MarketEvent
    from sqlalchemy import select, func
    import httpx
    import asyncio
    from datetime import datetime, timezone, timedelta

    async with async_session_factory() as db:
        result = await db.execute(
            select(Market).where(Market.clob_token_ids.isnot(None)).where(Market.resolved == False)
        )
        markets = list(result.scalars().all())

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_ts = int(cutoff.timestamp())
    created = 0
    errors = 0
    skipped = 0

    all_asset_ids = []
    asset_to_market = {}
    for m in markets:
        if not m.clob_token_ids:
            continue
        for tid in m.clob_token_ids:
            all_asset_ids.append(tid)
            asset_to_market[tid] = m

    sem = asyncio.Semaphore(concurrency)

    async def fetch_trades(asset_id: str):
        nonlocal created, errors
        market = asset_to_market[asset_id]
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        f"{settings.POLYMARKET_DATA_API_URL}/trades",
                        params={"asset": asset_id, "limit": limit_per_asset},
                    )
                    if resp.status_code != 200:
                        return
                    body = resp.json()
                    raw = body if isinstance(body, list) else body.get("value", [])
                new_events = []
                for t in raw:
                    ts = t.get("timestamp")
                    if not ts or int(ts) < cutoff_ts:
                        continue
                    new_events.append(MarketEvent(
                        market_id=market.id,
                        event_type="trade",
                        event_data={"source": "data_api_backfill", "original": t},
                        price=float(t["price"]) if t.get("price") else None,
                        size=float(t["size"]) if t.get("size") else None,
                        maker_address=t.get("proxyWallet"),
                        taker_address=None,
                        outcome=t.get("outcome"),
                        transaction_hash=t.get("transactionHash"),
                        timestamp=datetime.fromtimestamp(int(ts), tz=timezone.utc),
                    ))
                if new_events:
                    async with async_session_factory() as db:
                        for ev in new_events:
                            exists = await db.execute(
                                select(func.count()).select_from(MarketEvent)
                                .where(MarketEvent.market_id == ev.market_id)
                                .where(MarketEvent.transaction_hash == ev.transaction_hash)
                            )
                            if exists.scalar() > 0:
                                skipped += 1
                                continue
                            db.add(ev)
                            created += 1
                        await db.commit()
            except Exception:
                errors += 1

    batch_size = 50
    for i in range(0, len(all_asset_ids), batch_size):
        batch = all_asset_ids[i:i + batch_size]
        await asyncio.gather(*[fetch_trades(aid) for aid in batch])

    return {
        "events_created": created,
        "duplicates_skipped": skipped,
        "errors": errors,
        "assets_queried": len(all_asset_ids),
        "days_history": days,
    }


# Import and include routers
from app.api.router import router as api_router
app.include_router(api_router, prefix="/api/v1")
