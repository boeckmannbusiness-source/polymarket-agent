import uuid
from uuid import UUID
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Signal
from app.core.exceptions import MarketNotFoundError


class SignalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_signals(
        self,
        skip: int = 0,
        limit: int = 50,
        is_active: bool | None = None,
        signal_type: str | None = None,
        min_confidence: float | None = None,
    ) -> list[Signal]:
        query = select(Signal)
        if is_active is not None:
            query = query.where(Signal.is_active == is_active)
        if signal_type:
            query = query.where(Signal.signal_type == signal_type)
        if min_confidence is not None:
            query = query.where(Signal.confidence >= min_confidence)
        query = query.order_by(desc(Signal.generated_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_signal(self, signal_id: UUID) -> Signal:
        result = await self.db.execute(select(Signal).where(Signal.id == signal_id))
        signal = result.scalar_one_or_none()
        if not signal:
            raise MarketNotFoundError(f"Signal {signal_id} not found")
        return signal

    async def create_signal(
        self,
        market_id: UUID,
        signal_type: str,
        direction: str,
        confidence: float,
        implied_probability: float | None = None,
        estimated_probability: float | None = None,
        reasoning: str | None = None,
        source_agent: str | None = None,
        source_data: dict | None = None,
        ttl_minutes: int | None = None,
        correlation_id: str | None = None,
    ) -> Signal:
        expired_at = None
        if ttl_minutes:
            expired_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=ttl_minutes)

        cid = uuid.UUID(correlation_id) if correlation_id and isinstance(correlation_id, str) else correlation_id
        signal = Signal(
            market_id=market_id,
            signal_type=signal_type,
            direction=direction,
            confidence=confidence,
            implied_probability=implied_probability,
            estimated_probability=estimated_probability,
            reasoning=reasoning,
            source_agent=source_agent,
            source_data=source_data,
            expired_at=expired_at,
            correlation_id=cid,
        )
        self.db.add(signal)
        await self.db.flush()
        return signal
