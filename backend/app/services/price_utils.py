from decimal import Decimal
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MarketEvent


async def get_outcome_price(
    db: AsyncSession,
    market_id: Any,
    entry_ts: Any,
    direction: str | None = None,
    outcome: str | None = None,
) -> Decimal | None:
    event_result = await db.execute(
        select(MarketEvent.price, MarketEvent.outcome)
        .where(
            MarketEvent.market_id == market_id,
            MarketEvent.timestamp <= entry_ts,
        )
        .order_by(desc(MarketEvent.timestamp))
        .limit(1)
    )
    row = event_result.one_or_none()
    if not row or row[0] is None:
        return None

    price = Decimal(str(row[0]))
    event_outcome = row[1]
    if event_outcome and event_outcome.upper() == "NO":
        return Decimal("1") - price
    return price


async def get_outcome_specific_price(
    db: AsyncSession,
    market_id: Any,
    entry_ts: Any,
    signal_direction: str,
) -> Decimal | None:
    event_result = await db.execute(
        select(MarketEvent.price, MarketEvent.outcome)
        .where(
            MarketEvent.market_id == market_id,
            MarketEvent.timestamp <= entry_ts,
            MarketEvent.outcome.isnot(None),
        )
        .order_by(desc(MarketEvent.timestamp))
        .limit(1)
    )
    row = event_result.one_or_none()
    if not row or row[0] is None:
        return None

    price = Decimal(str(row[0]))
    event_outcome = row[1].upper() if row[1] else None
    if signal_direction == "BUY_YES":
        if event_outcome == "NO":
            return Decimal("1") - price
        return price
    elif signal_direction == "BUY_NO":
        if event_outcome == "YES":
            return Decimal("1") - price
        return price
    return Decimal(str(row[0]))
