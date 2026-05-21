import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)
    trade_type: Mapped[str] = mapped_column(String(16), nullable=False, default="paper")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False, default="market")
    size: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    filled_size: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    filled_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    slippage: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    pnl_percent: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    fee: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_check_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
