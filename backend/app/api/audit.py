from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.audit.execution_audit_service import ExecutionAuditService

router = APIRouter()


@router.get("/trade/{trade_id}")
async def audit_trade(trade_id: str, db: AsyncSession = Depends(get_db)):
    svc = ExecutionAuditService(db)
    return await svc.reconstruct_trade_path(trade_id)


@router.get("/system")
async def audit_system(db: AsyncSession = Depends(get_db)):
    svc = ExecutionAuditService(db)
    summary = await svc.system_audit_summary()
    orphans = await svc.detect_orphan_orders()
    duplicates = await svc.detect_duplicate_fills()
    return {"summary": summary, "orphan_orders": orphans, "duplicate_fills": duplicates}
