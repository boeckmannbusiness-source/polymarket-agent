from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.helius import HeliusTransaction
from app.services.helius_service import HeliusService
from app.services.notification_service import RateLimiter

router = APIRouter()

_webhook_rate_limiter = RateLimiter(max_per_minute=60)


@router.post("/helius")
async def helius_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    if not await _webhook_rate_limiter.allow():
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "60"},
        )

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
