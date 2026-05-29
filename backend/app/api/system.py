from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.system_mode import SystemMode, ModeManager

router = APIRouter()

_mode_manager: ModeManager | None = None


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
