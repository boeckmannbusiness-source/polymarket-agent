from fastapi import APIRouter

from app.api import health, markets, wallets, signals, trades, agents, strategies, portfolio, execution, backtesting, analytics, attribution

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(markets.router, prefix="/markets", tags=["markets"])
router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
router.include_router(signals.router, prefix="/signals", tags=["signals"])
router.include_router(trades.router, prefix="/trades", tags=["trades"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
router.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
router.include_router(execution.router, prefix="/execution", tags=["execution"])
router.include_router(backtesting.router, prefix="/backtesting", tags=["backtesting"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(attribution.router, prefix="/attribution", tags=["attribution"])
