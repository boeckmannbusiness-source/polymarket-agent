from datetime import datetime
from pydantic import BaseModel

from app.domain.execution import ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.replay.replay_seed import ReplaySeed


class ExecutionSnapshot(BaseModel):
    snapshot_id: str
    timestamp: datetime
    intent: ExecutionIntent
    plan: TransactionPlan
    seed: ReplaySeed
