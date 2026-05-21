import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import setup_logging, logger
from app.database import init_db
from app.redis import close_redis
from app.ingesters.polymarket_rest import PolymarketRESTIngester
from app.agents.orchestrator import Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("starting up", env=settings.APP_ENV, mode=settings.TRADING_MODE)
    try:
        await init_db()
        logger.info("database_initialized")
    except Exception as e:
        logger.warning("database_init_skipped", error=str(e))

    ingesters = [
        PolymarketRESTIngester(poll_interval=120),
    ]
    orchestrator = Orchestrator()

    bg_tasks = []
    for ing in ingesters:
        bg_tasks.append(asyncio.create_task(ing.run()))
    bg_tasks.append(asyncio.create_task(orchestrator.start_all()))

    logger.info("background_tasks_started", count=len(bg_tasks))

    yield

    logger.info("shutting_down")
    for ing in ingesters:
        await ing.stop()
    await orchestrator.stop_all()
    for t in bg_tasks:
        t.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    await close_redis()


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


# Import and include routers
from app.api.router import router as api_router
app.include_router(api_router, prefix="/api/v1")
