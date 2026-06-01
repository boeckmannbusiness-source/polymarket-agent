from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_log import AgentLog
from app.services.system_health_store import SystemHealthStore
from app.core.heartbeat import get_all_loop_heartbeats

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"ping": "pong"}


def _compute_status(last_heartbeat: datetime | None, cutoff: datetime) -> str:
    if last_heartbeat is None:
        return "never_seen"
    return "alive" if last_heartbeat >= cutoff else "stale"


@router.get("/heartbeats")
async def get_agent_heartbeats(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)

    result = await db.execute(
        select(
            AgentLog.agent_name,
            func.max(AgentLog.timestamp).label("last_heartbeat"),
        )
        .where(AgentLog.event_type == "heartbeat")
        .group_by(AgentLog.agent_name)
    )
    rows = list(result.all())
    now = datetime.now(timezone.utc)

    heartbeats: dict[str, dict] = {}
    for agent_name, last_heartbeat in rows:
        heartbeats[agent_name] = {
            "last_heartbeat": last_heartbeat.isoformat() if last_heartbeat else None,
            "status": _compute_status(last_heartbeat, cutoff),
        }

    # Add in-memory loop heartbeats
    loop_cutoff = now - timedelta(seconds=600)
    for loop_name, last_hb in get_all_loop_heartbeats().items():
        if loop_name not in heartbeats:
            heartbeats[loop_name] = {
                "last_heartbeat": last_hb.isoformat(),
                "status": _compute_status(last_hb, loop_cutoff),
                "source": "in_memory",
            }

    return heartbeats


@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)):
    store = SystemHealthStore(db)
    latest = store.get_latest()
    if not latest:
        latest = await store.record_snapshot()

    alerts = await store.check_alerts()

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    agent_result = await db.execute(
        select(
            AgentLog.agent_name,
            func.max(AgentLog.timestamp).label("last_heartbeat"),
        )
        .where(AgentLog.event_type == "heartbeat")
        .group_by(AgentLog.agent_name)
    )
    agent_rows = list(agent_result.all())
    now = datetime.now(timezone.utc)

    agents: dict[str, dict] = {}
    for agent_name, last_heartbeat in agent_rows:
        agents[agent_name] = {
            "last_heartbeat": last_heartbeat.isoformat() if last_heartbeat else None,
            "status": _compute_status(last_heartbeat, cutoff),
        }

    # Merge in-memory loop heartbeats
    loop_cutoff = now - timedelta(seconds=600)
    for loop_name, last_hb in get_all_loop_heartbeats().items():
        if loop_name not in agents:
            agents[loop_name] = {
                "last_heartbeat": last_hb.isoformat(),
                "status": _compute_status(last_hb, loop_cutoff),
                "source": "in_memory",
            }

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
        "agents": agents,
        "alerts": alerts,
    }
