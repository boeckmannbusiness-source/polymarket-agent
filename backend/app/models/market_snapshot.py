import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, Integer, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MarketStateSnapshot(Base):
    __tablename__ = "market_state_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True, index=True)
    condition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    spread: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    liquidity: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    orderbook_imbalance: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    volatility: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    volume_acceleration: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    whale_pressure: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    momentum: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    bid_depth: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    ask_depth: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    trade_count_1h: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_1h: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
