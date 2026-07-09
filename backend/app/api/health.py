from datetime import datetime, timezone, timedelta
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
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


@router.get("/live")
async def liveness():
    return {"status": "alive"}


async def _check_redis(timeout: float = 2.0) -> dict:
    try:
        from app.redis import get_redis
        r = await asyncio.wait_for(get_redis(), timeout=timeout)
        await asyncio.wait_for(r.ping(), timeout=timeout)
        return {"status": "ok", "latency_ms": 0}
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_database(timeout: float = 2.0) -> dict:
    try:
        async with get_db() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=timeout)
        return {"status": "ok"}
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_event_store(timeout: float = 2.0) -> dict:
    try:
        from app.redis import get_redis
        r = await asyncio.wait_for(get_redis(), timeout=timeout)
        exists = await asyncio.wait_for(r.exists("event_store"), timeout=timeout)
        return {"status": "ok" if exists else "empty", "exists": bool(exists)}
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_circuit_breakers(timeout: float = 2.0) -> dict:
    try:
        from app.services.risk.circuit_breakers import cb_system
        active = await asyncio.wait_for(cb_system.get_active(), timeout=timeout)
        return {"status": "ok", "active_breakers": len(active)}
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


async def _check_exchange(timeout: float = 2.0) -> dict:
    try:
        hbs = get_all_loop_heartbeats()
        relevant = {k: v for k, v in hbs.items() if "ingester" in k.lower() or "rest" in k.lower() or "ws" in k.lower()}
        now = datetime.now(timezone.utc)
        recent = [k for k, v in relevant.items() if now - v < timedelta(seconds=120)]
        return {
            "status": "ok" if recent else "stale",
            "recent_heartbeats": len(recent),
            "total_tracked": len(relevant),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/ready")
async def readiness():
    results = {}
    for check_name, check_fn in [
        ("redis", _check_redis),
        ("database", _check_database),
        ("event_store", _check_event_store),
        ("circuit_breakers", _check_circuit_breakers),
        ("exchange", _check_exchange),
    ]:
        try:
            results[check_name] = await asyncio.wait_for(check_fn(), timeout=3.0)
        except asyncio.TimeoutError:
            results[check_name] = {"status": "timeout"}
        except Exception as e:
            results[check_name] = {"status": "error", "detail": str(e)}

    all_healthy = all(r.get("status") == "ok" for r in results.values())
    return {"status": "healthy" if all_healthy else "degraded", "checks": results}


@router.get("/dependencies")
async def dependencies():
    return {
        "redis": await _check_redis(timeout=5.0),
        "database": await _check_database(timeout=5.0),
        "event_store": await _check_event_store(timeout=5.0),
        "circuit_breakers": await _check_circuit_breakers(timeout=5.0),
        "exchange": await _check_exchange(timeout=5.0),
        "scheduler": await _check_scheduler(timeout=5.0),
    }


async def _check_scheduler(timeout: float = 2.0) -> dict:
    try:
        from app.services.scheduler.task_scheduler import scheduler
        jobs = await asyncio.wait_for(scheduler.get_all_jobs(), timeout=timeout)
        return {"status": "ok", "job_count": len(jobs), "jobs": [j.get("name", "") for j in jobs]}
    except asyncio.TimeoutError:
        return {"status": "timeout"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
