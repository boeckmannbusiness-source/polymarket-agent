from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.system_health_store import SystemHealthStore

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"ping": "pong"}


@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    store = SystemHealthStore(db)
    # Note: in a real system, the store might be a singleton or loaded from cache
    # For now, we return the latest recorded snapshot if any
    latest = store.get_latest()
    if not latest:
        # Fallback to manual check if no background task has run yet
        latest = await store.record_snapshot()

    alerts = await store.check_alerts()

    return {
        "status": "healthy" if not alerts else "warning",
        "timestamp": latest.timestamp.isoformat(),
        "metrics": {
            "portfolio_value": latest.portfolio_value,
            "drawdown": latest.drawdown,
            "kill_switch_active": latest.kill_switch_active,
            "circuit_breaker_active": latest.circuit_breaker_active,
            "active_strategies": latest.active_strategies,
            "ws_events_last_minute": latest.ws_events_last_minute,
        },
        "alerts": alerts
    }
