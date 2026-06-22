from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ExecutionMode(str, Enum):
    DISABLED = "disabled"
    SIMULATION = "simulation"
    SANDBOX = "sandbox"
    LIVE = "live"


class ExecutionPermission(str, Enum):
    BUILD = "build"
    REPLAY = "replay"
    SIGN = "sign"
    RPC_READ = "rpc_read"
    RPC_SIMULATE = "rpc_simulate"
    RPC_WRITE = "rpc_write"
    CAPITAL_DEPLOY = "capital_deploy"


class AuthorizationDecision(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"


class ExecutionPolicy(BaseModel):
    mode: ExecutionMode
    allowed_permissions: List[ExecutionPermission]
    requires_explicit_approval: bool = False

    model_config = ConfigDict(frozen=True)


class ExecutionAuthorization(BaseModel):
    decision: AuthorizationDecision
    mode: ExecutionMode
    granted_permissions: List[ExecutionPermission]
    reason: Optional[str] = None
    timestamp: datetime
    fingerprint: Optional[str] = None

    def is_allowed(self, permission: ExecutionPermission) -> bool:
        return self.decision == AuthorizationDecision.GRANTED and permission in self.granted_permissions


# Default Policies
POLICIES = {
    ExecutionMode.DISABLED: ExecutionPolicy(
        mode=ExecutionMode.DISABLED,
        allowed_permissions=[],
    ),
    ExecutionMode.SIMULATION: ExecutionPolicy(
        mode=ExecutionMode.SIMULATION,
        allowed_permissions=[
            ExecutionPermission.BUILD,
            ExecutionPermission.REPLAY,
            ExecutionPermission.RPC_READ,
        ],
    ),
    ExecutionMode.SANDBOX: ExecutionPolicy(
        mode=ExecutionMode.SANDBOX,
        allowed_permissions=[
            ExecutionPermission.BUILD,
            ExecutionPermission.REPLAY,
            ExecutionPermission.SIGN,
            ExecutionPermission.RPC_READ,
            ExecutionPermission.RPC_SIMULATE,
        ],
    ),
    ExecutionMode.LIVE: ExecutionPolicy(
        mode=ExecutionMode.LIVE,
        allowed_permissions=[
            ExecutionPermission.BUILD,
            ExecutionPermission.REPLAY,
            ExecutionPermission.SIGN,
            ExecutionPermission.RPC_READ,
            ExecutionPermission.RPC_SIMULATE,
            ExecutionPermission.RPC_WRITE,
            ExecutionPermission.CAPITAL_DEPLOY,
        ],
        requires_explicit_approval=True,
    ),
}
