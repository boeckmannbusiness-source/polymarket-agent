from fastapi import APIRouter

from app.api import health, markets, wallets, signals, trades, agents

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(markets.router, prefix="/markets", tags=["markets"])
router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
router.include_router(signals.router, prefix="/signals", tags=["signals"])
router.include_router(trades.router, prefix="/trades", tags=["trades"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
