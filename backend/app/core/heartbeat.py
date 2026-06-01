from datetime import datetime, timezone

from app.database import async_session_factory
from app.models.agent_log import AgentLog
from app.core.logging import logger


# In-memory heartbeat registry for background loops
_loop_heartbeats: dict[str, datetime] = {}


def touch_loop_heartbeat(loop_name: str):
    """Record an in-memory heartbeat for a background loop.
    This is lightweight (no DB write) and used by the health endpoint
    to detect stale background tasks.
    """
    _loop_heartbeats[loop_name] = datetime.now(timezone.utc)


def get_loop_heartbeat(loop_name: str) -> datetime | None:
    return _loop_heartbeats.get(loop_name)


def get_all_loop_heartbeats() -> dict[str, datetime]:
    return dict(_loop_heartbeats)


async def record_heartbeat(agent_name: str, event_type: str = "heartbeat", data: dict | None = None):
    """Record a persistent heartbeat entry in AgentLog.
    Use sparingly (every 5+ minutes) to avoid DB write amplification.
    """
    try:
        async with async_session_factory() as db:
            entry = AgentLog(
                agent_name=agent_name,
                event_type=event_type,
                data=data or {},
                timestamp=datetime.now(timezone.utc),
            )
            db.add(entry)
            await db.commit()
    except Exception as e:
        logger.warning("heartbeat_record_failed", agent=agent_name, error=str(e))
