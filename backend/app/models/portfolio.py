import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)
    market_condition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    strategy_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    total_exposure: Mapped[float] = mapped_column(Numeric(24, 8), default=0.0)
    cash_reserve: Mapped[float] = mapped_column(Numeric(24, 8), default=0.0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    total_unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    total_realized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    portfolio_value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    peak_value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    drawdown: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    category_exposure: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MarketCorrelation(Base):
    __tablename__ = "market_correlations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=False)
    market_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=False)
    correlation_coefficient: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
