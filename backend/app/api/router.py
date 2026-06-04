from fastapi import APIRouter

from app.api import health, markets, wallets, signals, trades, agents, strategies, execution, backtesting, analytics, attribution, trace, system, cockpit
from app.api import events as events_router
from app.api import control as control_router
from app.api import incidents as incidents_router
from app.api import audit as audit_router
from app.api import operations as operations_router
from app.api.monitoring import execution_routes as monitoring_routes
from app.api.portfolio import router as portfolio_router
from app.api import shadow as shadow_router
from app.api import shadow_analytics as shadow_analytics_router
from app.api import redis_status as redis_status_router
from app.api import tournament as tournament_router
from app.api.research import router as research_router
from app.api.research_agents import router as research_agents_router

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(markets.router, prefix="/markets", tags=["markets"])
router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
router.include_router(signals.router, prefix="/signals", tags=["signals"])
router.include_router(trades.router, prefix="/trades", tags=["trades"])
router.include_router(agents.router, prefix="/agents", tags=["agents"])
router.include_router(strategies.router, prefix="/strategies", tags=["strategies"])
router.include_router(portfolio_router, prefix="/portfolio", tags=["portfolio"])
router.include_router(execution.router, prefix="/execution", tags=["execution"])
router.include_router(backtesting.router, prefix="/backtesting", tags=["backtesting"])
router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
router.include_router(attribution.router, prefix="/attribution", tags=["attribution"])
router.include_router(trace.router, prefix="/trace", tags=["trace"])
router.include_router(system.router, prefix="/system", tags=["system"])
router.include_router(cockpit.router, prefix="/cockpit", tags=["cockpit"])
router.include_router(monitoring_routes.router, prefix="/monitoring", tags=["monitoring"])
router.include_router(events_router.router, prefix="/events", tags=["events"])
router.include_router(control_router.router, prefix="/control", tags=["control"])
router.include_router(incidents_router.router, prefix="/incidents", tags=["incidents"])
router.include_router(audit_router.router, prefix="/audit", tags=["audit"])
router.include_router(operations_router.router, prefix="/operations", tags=["operations"])
router.include_router(shadow_router.router, prefix="/shadow", tags=["shadow"])
router.include_router(shadow_analytics_router.router, prefix="/shadow", tags=["shadow"])
router.include_router(redis_status_router.router, prefix="/system", tags=["system"])
router.include_router(tournament_router.router, prefix="/tournament", tags=["tournament"])
router.include_router(research_agents_router, prefix="/research-agents", tags=["research_agents"])
