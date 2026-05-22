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


@app.post("/debug/backfill-events")
async def backfill_events():
    from app.database import async_session_factory
    from app.models import Market, MarketEvent
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    import random

    now = datetime.now(timezone.utc)
    async with async_session_factory() as db:
        result = await db.execute(select(Market))
        markets = list(result.scalars().all())
        count = 0
        for market in markets[:50]:
            for i in range(5):
                price = round(random.uniform(0.1, 0.9), 4)
                vol = float(market.volume) if market.volume else 1000
                event = MarketEvent(
                    market_id=market.id, event_type="trade", price=price,
                    size=vol / 20,
                    maker_address=None, taker_address=None,
                    side="buy" if i < 10 else "sell",
                    outcome="YES" if price > 0.5 else "NO",
                    timestamp=now - timedelta(hours=i * 6),
                )
                db.add(event)
                count += 1
        await db.commit()
        return {"events_created": count}


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
