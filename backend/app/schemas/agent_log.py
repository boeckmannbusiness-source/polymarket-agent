from datetime import datetime

from pydantic import BaseModel


class AgentLogResponse(BaseModel):
    id: int
    agent_name: str
    event_type: str
    data: dict | None = None
    timestamp: datetime | None = None

    model_config = {"from_attributes": True}
