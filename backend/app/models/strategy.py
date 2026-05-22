import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Text, Integer
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class StrategyConfigRecord(Base):
    __tablename__ = "strategy_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StrategyPerformanceRecord(Base):
    __tablename__ = "strategy_performances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    executed_signals: Mapped[int] = mapped_column(Integer, default=0)
    winning_signals: Mapped[int] = mapped_column(Integer, default=0)
    losing_signals: Mapped[int] = mapped_column(Integer, default=0)
    total_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    avg_confidence: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
