from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.helius import HeliusTransaction
from app.services.helius_service import HeliusService

router = APIRouter()


@router.post("/helius")
async def helius_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth = request.headers.get("Authorization", "")
    if settings.HELIUS_WEBHOOK_SECRET and auth != f"Bearer {settings.HELIUS_WEBHOOK_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    raw = await request.json()
    if not isinstance(raw, list):
        raw = raw.get("transactions", raw) if isinstance(raw, dict) else []

    transactions = [HeliusTransaction(**tx) for tx in raw]

    service = HeliusService(db)
    count = await service.process_batch(transactions)

    return {"status": "ok", "processed": count}
