from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.domain.execution_authorization.models import ExecutionMode, ExecutionPermission, AuthorizationDecision


class ExecutionAuditRecord(BaseModel):
    mode: ExecutionMode
    decision: AuthorizationDecision
    reason: Optional[str] = None
    permissions: List[ExecutionPermission]
    fingerprint: Optional[str] = None
    timestamp: datetime
    context: Optional[dict] = None
