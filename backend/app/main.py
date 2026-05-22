import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging, logger
from app.database import init_db
from app.redis import close_redis
from app.ingesters.polymarket_rest import PolymarketRESTIngester
from app.ingesters.polymarket_ws import PolymarketWSIngester
from app.agents.orchestrator import Orchestrator
from app.services.event_bridge import EventPersistenceBridge


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting_up", env=settings.APP_ENV, mode=settings.TRADING_MODE)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    rest_ingester = PolymarketRESTIngester(poll_interval=60)
    ws_ingester = PolymarketWSIngester()
    bridge = EventPersistenceBridge()
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


# Import and include routers
from app.api.router import router as api_router
app.include_router(api_router, prefix="/api/v1")
