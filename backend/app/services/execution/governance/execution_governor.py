import uuid
from datetime import datetime, timezone
from typing import Optional

from app.domain.execution_authorization.models import (
    ExecutionMode,
    ExecutionPermission,
    ExecutionAuthorization,
    AuthorizationDecision,
    POLICIES,
)
from app.core.logging import logger
from app.services.audit.audit_logger import emit
from app.domain.execution_authorization.audit import ExecutionAuditRecord


class ExecutionAuthorizationError(Exception):
    pass


class ExecutionGovernor:
    def __init__(self, mode: ExecutionMode):
        self._mode = mode
        self._policy = POLICIES.get(mode) or POLICIES[ExecutionMode.DISABLED]

    def authorize(self, permission: ExecutionPermission, context: Optional[dict] = None) -> ExecutionAuthorization:
        decision = AuthorizationDecision.DENIED
        reason = None
        granted_permissions = []

        if permission in self._policy.allowed_permissions:
            if self._policy.requires_explicit_approval:
                decision = AuthorizationDecision.REQUIRES_APPROVAL
                reason = "Explicit approval required for LIVE mode"
            else:
                decision = AuthorizationDecision.GRANTED
                granted_permissions = self._policy.allowed_permissions
        else:
            reason = f"Permission {permission} not allowed in {self._mode} mode"

        auth = ExecutionAuthorization(
            decision=decision,
            mode=self._mode,
            granted_permissions=granted_permissions,
            reason=reason,
            timestamp=datetime.now(timezone.utc),
            fingerprint=(context.get("fingerprint") or context.get("trace_id")) if context else None,
        )

        # Create audit record
        audit_record = ExecutionAuditRecord(
            mode=self._mode,
            decision=decision,
            reason=reason,
            permissions=granted_permissions,
            fingerprint=auth.fingerprint,
            timestamp=auth.timestamp,
            context=context,
        )

        # Audit decision
        logger.info(
            "execution_governance_decision",
            **audit_record.model_dump()
        )

        return auth

    def authorize_execution(self, context: Optional[dict] = None) -> None:
        auth = self.authorize(ExecutionPermission.BUILD, context)
        if not auth.is_allowed(ExecutionPermission.BUILD):
            raise ExecutionAuthorizationError(f"Execution forbidden: {auth.reason}")

    def authorize_sign(self, context: Optional[dict] = None) -> None:
        auth = self.authorize(ExecutionPermission.SIGN, context)
        if not auth.is_allowed(ExecutionPermission.SIGN):
            raise ExecutionAuthorizationError(f"Signing forbidden: {auth.reason}")

    def authorize_rpc(self, write: bool = False, context: Optional[dict] = None) -> None:
        permission = ExecutionPermission.RPC_WRITE if write else ExecutionPermission.RPC_READ
        auth = self.authorize(permission, context)
        if not auth.is_allowed(permission):
            raise ExecutionAuthorizationError(f"RPC { 'write' if write else 'read' } forbidden: {auth.reason}")

    def authorize_simulate(self, context: Optional[dict] = None) -> None:
        auth = self.authorize(ExecutionPermission.RPC_SIMULATE, context)
        if not auth.is_allowed(ExecutionPermission.RPC_SIMULATE):
            raise ExecutionAuthorizationError(f"RPC simulation forbidden: {auth.reason}")

    def authorize_capital(self, context: Optional[dict] = None) -> None:
        auth = self.authorize(ExecutionPermission.CAPITAL_DEPLOY, context)
        if not auth.is_allowed(ExecutionPermission.CAPITAL_DEPLOY):
            raise ExecutionAuthorizationError(f"Capital deployment forbidden: {auth.reason}")
