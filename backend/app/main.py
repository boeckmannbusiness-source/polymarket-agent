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
async def debug_replay_drift(strategy: str = "whale_following", hours: float = 1, max_events: int = 2000):
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
            return {"error": "no events in DB"}
        end = latest_ts - timedelta(minutes=1)
        start = end - timedelta(hours=hours)
        r = await db.execute(
            select(func.count()).select_from(MarketEvent)
            .where(MarketEvent.timestamp.between(start, end))
        )
        total = r.scalar()
        while total > max_events and hours > 0.001:
            hours /= 10
            start = end - timedelta(hours=hours)
            r = await db.execute(
                select(func.count()).select_from(MarketEvent)
                .where(MarketEvent.timestamp.between(start, end))
            )
            total = r.scalar()
    if total > max_events:
        return {"error": f"could not find window under {max_events} events (min was {total})"}

    drift_fields = ["strategy_name", "entry_timestamp", "entry_price",
                    "outcome_5m", "outcome_15m", "outcome_1h", "outcome_4h", "outcome_close",
                    "pnl_5m", "pnl_15m", "pnl_1h", "pnl_4h", "pnl_close",
                    "max_favorable_excursion", "max_adverse_excursion",
                    "execution_slippage", "execution_fill_price"]

    async with async_session_factory() as db:
        engine = ReplayEngine(db, ExecutionSimulator())
        result = await engine.run(strategy, start, end, ReplayMode.SIGNAL_ONLY, signal_interval_seconds=1)
        rows = [str([getattr(s, f, None) for f in drift_fields]) for s in result.signals]
        h = hashlib.sha256("|".join(rows).encode()).hexdigest()

    return {
        "determinism_check": "call this endpoint twice and compare hashes",
        "hash": h,
        "signal_count": len(result.signals),
        "events_processed": result.total_events_processed,
        "window_hours": hours,
        "total_in_window": total,
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


@app.get("/debug/ws-events")
async def debug_ws_events():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    return {
        "raw_events": _ws_ingester.last_raw_events[-50:],
        "event_type_counts": _ws_ingester.stats.get("event_type_counts", {}),
        "total_messages": _ws_ingester.stats.get("messages_received", 0),
    }


@app.get("/debug/event-stats")
async def debug_event_stats():
    if _ws_ingester is None:
        return {"error": "ws_ingester_not_initialized"}
    ws = _ws_ingester.event_stats
    bridge = _bridge.stats if _bridge else {}
    return {
        "ws_ingester": ws,
        "event_bridge": {
            "events_by_type": bridge.get("events_by_type", {}),
            "persisted_by_type": bridge.get("persisted_by_type", {}),
            "dropped_by_type": bridge.get("dropped_by_type", {}),
            "duplicate_events_detected": bridge.get("duplicate_events_detected", 0),
        },
        "classification_health": {
            "unknown_event_types": list(ws.get("unknown_by_type", {}).keys()),
            "total_unknown": sum(ws.get("unknown_by_type", {}).values()),
            "total_dropped": ws.get("total_dropped", 0),
            "validation_failures": ws.get("validation_failures", 0),
            "duplicates_ingester": ws.get("duplicate_events_detected", 0),
            "duplicates_bridge": bridge.get("duplicate_events_detected", 0),
        },
    }


@app.get("/debug/live-pipeline")
async def debug_live_pipeline():
    from app.redis import get_redis
    result = {
        "ws_ingester": None,
        "event_bridge": None,
        "redis_stream": None,
        "pipeline_flow": {
            "ws_received": 0,
            "ws_parsed": 0,
            "ws_normalized": 0,
            "bridge_processed": 0,
            "db_persisted": 0,
            "end_to_end_health": "unknown",
            "overall_loss_rate_pct": 0,
            "loss_by_type": {},
        },
    }
    if _ws_ingester:
        s = _ws_ingester.stats
        result["ws_ingester"] = {
            "connected": s.get("connected"),
            "messages_received": s.get("messages_received"),
            "parsed_events": s.get("parsed_events"),
            "normalized_events_published": s.get("normalized_events_published"),
            "parse_failures": s.get("parse_failures"),
            "subscribed_assets": s.get("subscribed_assets"),
            "last_message_time": s.get("last_message_time"),
            "reconnect_count": s.get("reconnect_count"),
            "event_type_counts": s.get("event_type_counts"),
        }
        result["pipeline_flow"]["ws_received"] = s.get("messages_received", 0)
        result["pipeline_flow"]["ws_parsed"] = s.get("parsed_events", 0)
        result["pipeline_flow"]["ws_normalized"] = s.get("normalized_events_published", 0)
    if _bridge:
        b = _bridge.stats
        result["event_bridge"] = {
            "events_processed": b.get("events_processed"),
            "persisted_count": b.get("persisted_count"),
            "failed_count": b.get("failed_count"),
            "retry_count": b.get("retry_count"),
            "dlq_size": b.get("dlq_size"),
            "events_by_type": b.get("events_by_type"),
            "persisted_by_type": b.get("persisted_by_type"),
            "dropped_by_type": b.get("dropped_by_type"),
            "duplicate_events_detected": b.get("duplicate_events_detected"),
        }
        result["pipeline_flow"]["bridge_processed"] = b.get("events_processed", 0)
        result["pipeline_flow"]["db_persisted"] = b.get("persisted_count", 0)
        # Per-type loss
        persisted_by_type = b.get("persisted_by_type", {})
        events_by_type = b.get("events_by_type", {})
        loss = {}
        for etype, total in events_by_type.items():
            persisted = persisted_by_type.get(etype, 0)
            loss[etype] = round((1 - persisted / (total or 1)) * 100, 1)
        result["pipeline_flow"]["loss_by_type"] = loss
    try:
        r = await get_redis()
        info = await r.xinfo_stream("market:data")
        result["redis_stream"] = {
            "length": info.get("length", 0),
            "radix_tree_keys": info.get("radix-tree-keys", 0),
            "radix_tree_nodes": info.get("radix-tree-nodes", 0),
            "last_generated_id": info.get("last-generated-id"),
        }
    except Exception as e:
        result["redis_stream"] = {"error": str(e)}
    ws_rx = result["pipeline_flow"]["ws_received"]
    ws_parsed = result["pipeline_flow"]["ws_parsed"]
    bridge_proc = result["pipeline_flow"]["bridge_processed"]
    persisted = result["pipeline_flow"]["db_persisted"]
    if ws_rx == 0:
        result["pipeline_flow"]["end_to_end_health"] = "no_data"
    elif ws_parsed == 0:
        result["pipeline_flow"]["end_to_end_health"] = "ingester_unparsed"
    elif bridge_proc == 0:
        result["pipeline_flow"]["end_to_end_health"] = "bridge_drop"
    elif persisted == 0:
        result["pipeline_flow"]["end_to_end_health"] = "db_write_drop"
    else:
        result["pipeline_flow"]["end_to_end_health"] = "healthy"
    result["pipeline_flow"]["overall_loss_rate_pct"] = (
        round((1 - persisted / (ws_rx or 1)) * 100, 1)
    )
    return result


@app.get("/debug/live-trace/{event_id}")
async def debug_live_trace(event_id: str):
    from app.database import async_session_factory
    from sqlalchemy import select
    from app.models import MarketEvent, Market
    from app.models import Signal, Trade
    from datetime import timedelta

    def _sf(v):
        if v is None: return None
        try: return float(v)
        except (ValueError, TypeError): return None

    if _ws_ingester is None or _bridge is None:
        return {"error": "ingester or bridge not initialized"}

    trace = {
        "trace_id": event_id,
        "ws_raw": None,
        "normalized_event": None,
        "validation": {"valid": None, "reason": None},
        "duplicate_check": {"is_duplicate": None},
        "redis_stream": None,
        "bridge_consumed": None,
        "bridge_dlq": False,
        "db_persisted": None,
        "strategy_signals": [],
        "execution": [],
    }

    ws_traces = _ws_ingester.live_traces
    normalized = ws_traces.get(event_id)
    if not normalized:
        return {"error": f"event_id '{event_id}' not found in live traces", "trace": trace}

    # 1. WS raw (if stored in _last_raw_events)
    for raw in _ws_ingester.last_raw_events:
        if raw.get("received_at", "").startswith(normalized.get("_normalized_at", "")[:19]):
            trace["ws_raw"] = raw
            break

    # 2. Normalized event
    trace["normalized_event"] = normalized

    # 3. Schema validation check
    from app.ingesters.polymarket_ws import PolymarketWSIngester
    valid, reason = PolymarketWSIngester._validate_normalized(normalized)
    trace["validation"] = {"valid": valid, "reason": reason}

    # 4. Duplicate check
    event_hash = PolymarketWSIngester._compute_event_hash(normalized)
    trace["duplicate_check"] = {"hash": event_hash[:16]}

    # 5. Redis stream (check if event made it to stream)
    try:
        from app.redis import get_redis
        r = await get_redis()
        info = await r.xinfo_stream("market:data")
        trace["redis_stream"] = {
            "length": info.get("length", 0),
        }
        # Check pending for this consumer group
        pending = await r.xpending("market:data", "persistence_bridge")
        trace["bridge_consumed"] = {
            "pending_count": pending.get("pending", 0) if pending else 0,
        }
    except Exception as e:
        trace["redis_stream"] = {"error": str(e)}

    # 6. DB persistence
    condition_id = normalized.get("condition_id") or normalized.get("conditionId")
    price = normalized.get("price")
    timestamp = normalized.get("timestamp")
    if condition_id:
        async with async_session_factory() as db:
            m = await db.execute(
                select(Market).where(Market.condition_id == condition_id)
            )
            m = m.scalar_one_or_none()
            if m:
                events = await db.execute(
                    select(MarketEvent)
                    .where(MarketEvent.market_id == m.id)
                    .where(MarketEvent.price == (_sf(price) if price else None))
                    .order_by(MarketEvent.timestamp.desc())
                    .limit(5)
                )
                trace["db_persisted"] = [
                    {
                        "id": e.id,
                        "event_type": e.event_type,
                        "price": float(e.price) if e.price else None,
                        "size": float(e.size) if e.size else None,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    }
                    for e in events.scalars().all()
                ]
                # 7. Strategy signals from this market
                if trace["db_persisted"]:
                    latest_ts = trace["db_persisted"][0].get("timestamp")
                    if latest_ts:
                        cutoff = datetime.fromisoformat(latest_ts.replace("Z", "+00:00")) - timedelta(seconds=5)
                        signals = await db.execute(
                            select(Signal)
                            .where(Signal.market_id == m.id)
                            .where(Signal.created_at >= cutoff)
                            .order_by(Signal.created_at.desc())
                            .limit(5)
                        )
                        trace["strategy_signals"] = [
                            {
                                "id": s.id,
                                "strategy": s.strategy_name,
                                "signal": s.signal,
                                "confidence": float(s.confidence) if s.confidence else None,
                                "price": float(s.entry_price) if s.entry_price else None,
                                "created_at": s.created_at.isoformat() if s.created_at else None,
                            }
                            for s in signals.scalars().all()
                        ]
                        # 8. Paper trades from signals
                        if trace["strategy_signals"]:
                            signal_ids = [s["id"] for s in trace["strategy_signals"]]
                            trades = await db.execute(
                                select(Trade)
                                .where(Trade.signal_id.in_(signal_ids))
                                .limit(5)
                            )
                            trace["execution"] = [
                                {
                                    "id": t.id,
                                    "side": t.side,
                                    "outcome": t.outcome,
                                    "size": float(t.size) if t.size else None,
                                    "price": float(t.entry_price) if t.entry_price else None,
                                    "status": t.status,
                                    "created_at": t.created_at.isoformat() if t.created_at else None,
                                }
                                for t in trades.scalars().all()
                            ]

    trace["bridge_dlq_size"] = _bridge.stats.get("dlq_size", 0)

    return trace


@app.get("/debug/redis-test")
async def debug_redis_test():
    from app.redis import get_redis
    from datetime import datetime, timezone
    import uuid, json
    results = {"steps": {}}
    try:
        r = await get_redis()
        results["steps"]["connected"] = True
        pong = await r.ping()
        results["steps"]["ping"] = pong
        test_id = str(uuid.uuid4())
        test_data = {"test": True, "id": test_id, "ts": datetime.now(timezone.utc).isoformat()}
        xid = await r.xadd("test:stream", test_data, maxlen=100)
        results["steps"]["xadd_success"] = True
        results["steps"]["xid"] = xid
        read_back = await r.xrange("test:stream", count=1)
        results["steps"]["xrange_count"] = len(read_back)
        await r.delete("test:stream")
        results["steps"]["cleanup"] = True
    except Exception as e:
        results["steps"]["error"] = str(e)
        import traceback
        results["steps"]["traceback"] = traceback.format_exc()
    return results


@app.get("/debug/replay-consistency")
async def debug_replay_consistency(days: float = 1):
    from app.database import async_session_factory
    from app.replay.engine import ReplayEngine, ReplayMode
    from app.services.execution_simulator import ExecutionSimulator
    from app.models import Signal
    from sqlalchemy import select, func
    from datetime import datetime, timezone, timedelta
    import hashlib

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    async with async_session_factory() as db:
        # Live signals from DB
        live_result = await db.execute(
            select(Signal)
            .where(Signal.generated_at.between(start, now))
            .order_by(Signal.generated_at.asc())
        )
        live_signals = list(live_result.scalars().all())

        # Replay signals from same window
        engine = ReplayEngine(db, ExecutionSimulator())
        replay_result = await engine.run(
            strategy_name=None,
            start_time=start,
            end_time=now,
            mode=ReplayMode.SIGNAL_ONLY,
            signal_interval_seconds=60,
        )

    replay_signals = replay_result.signals

    # Aggregate comparison: count by strategy
    live_by_strategy: dict[str, int] = {}
    for s in live_signals:
        key = f"{s.signal_type}:{s.direction}"
        live_by_strategy[key] = live_by_strategy.get(key, 0) + 1

    replay_by_strategy: dict[str, int] = {}
    for s in replay_signals:
        key = f"{s.signal.signal}:{s.strategy_name}"
        replay_by_strategy[key] = replay_by_strategy.get(key, 0) + 1

    # Determinism check: replay twice and compare hashes
    async with async_session_factory() as db:
        engine2 = ReplayEngine(db, ExecutionSimulator())
        replay2 = await engine2.run(
            strategy_name=None,
            start_time=start,
            end_time=now,
            mode=ReplayMode.SIGNAL_ONLY,
            signal_interval_seconds=60,
        )

    rows1 = [f"{s.signal.signal}|{s.entry_price}|{s.entry_timestamp}" for s in replay_signals]
    rows2 = [f"{s.signal.signal}|{s.entry_price}|{s.entry_timestamp}" for s in replay2.signals]
    hash1 = hashlib.sha256("|".join(rows1).encode()).hexdigest()
    hash2 = hashlib.sha256("|".join(rows2).encode()).hexdigest()
    deterministic = hash1 == hash2

    return {
        "window_hours": days * 24,
        "window_events": replay_result.total_events_processed,
        "live_signals_count": len(live_signals),
        "live_by_strategy": live_by_strategy,
        "replay_signals_count": len(replay_signals),
        "replay_by_strategy": replay_by_strategy,
        "replay_deterministic": deterministic,
        "replay_drift_hash": hash1,
        "consistency_note": (
            "replay and live signal counts compared by strategy-type distribution. "
            "exact 1:1 matching requires shared trace_ids between WS and signals."
        ),
    }


# Import and include routers
from app.api.router import router as api_router
app.include_router(api_router, prefix="/api/v1")
