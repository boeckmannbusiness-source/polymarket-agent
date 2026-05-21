from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.agent_log import AgentLogResponse
from app.services.market_service import MarketService

router = APIRouter()


@router.get("/logs")
async def get_agent_logs(
    agent_name: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[AgentLogResponse]:
    from app.services import AgentLogService

    service = AgentLogService(db)
    return await service.get_logs(agent_name=agent_name, limit=limit)


@router.get("/status")
async def get_agent_status():
    return {"orchestrator": "running", "agents": {}}
