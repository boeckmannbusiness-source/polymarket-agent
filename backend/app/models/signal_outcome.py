import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Integer, ForeignKey, BigInteger
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True, index=True)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)

    entry_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_probability: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    entry_confidence: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)

    outcome_5m: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probability_5m: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_5m: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    outcome_15m: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probability_15m: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_15m: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    outcome_1h: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probability_1h: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_1h: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    outcome_4h: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probability_4h: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_4h: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    outcome_close: Mapped[str | None] = mapped_column(String(8), nullable=True)
    probability_close: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_close: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    max_favorable_excursion: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    max_adverse_excursion: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    reversal_count: Mapped[int] = mapped_column(Integer, default=0)
    reversal_probability: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)

    realized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    holding_time_seconds: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    evaluation_epoch: Mapped[str] = mapped_column(String(32), default="legacy")
    signal_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)

    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
