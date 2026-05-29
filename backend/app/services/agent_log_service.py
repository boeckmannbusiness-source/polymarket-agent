import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentLog


class AgentLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(self, agent_name: str, event_type: str, data: dict | None = None, correlation_id: str | None = None):
        cid = uuid.UUID(correlation_id) if correlation_id and isinstance(correlation_id, str) else correlation_id
        entry = AgentLog(
            agent_name=agent_name,
            event_type=event_type,
            data=data,
            correlation_id=cid,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def get_logs(
        self,
        agent_name: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[AgentLog]:
        query = select(AgentLog)
        if agent_name:
            query = query.where(AgentLog.agent_name == agent_name)
        if event_type:
            query = query.where(AgentLog.event_type == event_type)
        query = query.order_by(desc(AgentLog.timestamp)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_agent_summary(self, agent_name: str, since: datetime | None = None) -> dict:
        query = select(AgentLog).where(AgentLog.agent_name == agent_name)
        if since:
            query = query.where(AgentLog.timestamp >= since)
        result = await self.db.execute(query.order_by(AgentLog.timestamp))
        logs = list(result.scalars().all())

        summary = {
            "agent_name": agent_name,
            "total_events": len(logs),
            "event_types": {},
            "last_event": logs[-1].timestamp.isoformat() if logs else None,
        }
        for log in logs:
            summary["event_types"][log.event_type] = summary["event_types"].get(log.event_type, 0) + 1
        return summary
