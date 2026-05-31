from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

from app.core.system_mode import SystemMode, ModeManager

router = APIRouter()

from app.config import settings

_mode_manager: ModeManager | None = None


async def _require_admin(x_admin_key: str = Header(default="")):
    if settings.ADMIN_API_KEY:
        if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")


def set_mode_manager(mgr: ModeManager):
    global _mode_manager
    _mode_manager = mgr


class ModeOverrideRequest(BaseModel):
    mode: str
    reason: str = ""
    operator: str = ""
    ttl_seconds: int = 300


class ModeOverrideResponse(BaseModel):
    mode: str
    reason: str
    is_manual_override: bool
    ttl_seconds: int | None


@router.get("/mode")
async def get_system_mode():
    if not _mode_manager:
        raise HTTPException(status_code=503, detail="Mode manager not initialized")
    snapshot = await _mode_manager.get_snapshot()
    return {
        "mode": snapshot.mode.value,
        "reason": snapshot.reason,
        "is_manual_override": snapshot.is_manual_override,
        "operator": snapshot.operator or "",
        "updated_at": snapshot.updated_at,
        "ttl_seconds": snapshot.ttl_seconds,
    }


@router.post("/mode", response_model=ModeOverrideResponse)
async def set_system_mode(request: ModeOverrideRequest):
    if not _mode_manager:
        raise HTTPException(status_code=503, detail="Mode manager not initialized")
    try:
        target = SystemMode(request.mode.lower())
    except ValueError:
        valid = [m.value for m in SystemMode]
        raise HTTPException(status_code=400, detail=f"Invalid mode. Valid: {valid}")

    await _mode_manager.set_manual_override(
        mode=target,
        reason=request.reason or f"manual_override_by_{request.operator or 'unknown'}",
        operator=request.operator,
        ttl_seconds=max(request.ttl_seconds, 60),
    )
    return ModeOverrideResponse(
        mode=target.value,
        reason=request.reason,
        is_manual_override=True,
        ttl_seconds=request.ttl_seconds,
    )


@router.delete("/mode")
async def clear_system_mode():
    if not _mode_manager:
        raise HTTPException(status_code=503, detail="Mode manager not initialized")
    await _mode_manager.clear_manual_override()
    return {"status": "override_cleared"}


class AuditLogRequest(BaseModel):
    telegram_user: str
    command: str
    result: str
    extra_data: dict | None = None


@router.post("/remote/audit")
async def log_remote_audit(
    request: AuditLogRequest,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin)
):
    from app.models.remote_audit import RemoteControlAudit
    audit = RemoteControlAudit(
        telegram_user=request.telegram_user,
        command=request.command,
        result=request.result,
        extra_data=request.extra_data
    )
    db.add(audit)
    await db.commit()
    return {"status": "ok"}
