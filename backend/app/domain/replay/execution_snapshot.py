from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from app.domain.execution_authorization.models import ExecutionMode, ExecutionPermission, AuthorizationDecision
from app.domain.execution import ExecutionIntent
from app.domain.planning.transaction_plan import TransactionPlan
from app.domain.replay.replay_seed import ReplaySeed


class ExecutionSnapshot(BaseModel):
    snapshot_id: str
    timestamp: datetime
    intent: ExecutionIntent
    plan: TransactionPlan
    seed: ReplaySeed


class ExecutionAuthorizationSnapshot(BaseModel):
    decision: AuthorizationDecision
    mode: ExecutionMode
    granted_permissions: List[ExecutionPermission]
    reason: Optional[str] = None
    timestamp: datetime
    fingerprint: Optional[str] = None
