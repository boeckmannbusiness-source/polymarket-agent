from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.recovery.order_recovery_service import OrderRecoveryService
from app.services.reliability.dead_letter_queue import dlq

router = APIRouter()


@router.post("/recovery/run")
async def run_order_recovery(
    force: bool = Query(False, description="Skip idempotency guard"),
    recovery_window: int = Query(60, description="Recovery window in minutes"),
    db: AsyncSession = Depends(get_db),
):
    svc = OrderRecoveryService(db)
    report = await svc.run_scan(recovery_window_minutes=recovery_window, force=force)
    return report


@router.get("/dlq")
async def get_dlq(
    domain: str | None = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=500),
):
    events = await dlq.get_events(domain=domain, limit=limit)
    stats = await dlq.get_stats()
    return {"events": events, "count": len(events), "stats": stats}


@router.post("/dlq/replay")
async def replay_dlq(
    domain: str | None = Query(None, description="Replay only this domain"),
    limit: int = Query(100, ge=1, le=1000),
):
    result = await dlq.replay(domain=domain, limit=limit)
    return result
