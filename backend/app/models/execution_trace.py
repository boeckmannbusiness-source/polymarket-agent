import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trades.id"), nullable=True, index=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True, index=True)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)

    signal_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    risk_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)

    execution_side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    execution_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_size: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    fill_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fill_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    fill_size: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    slippage: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    fee: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    stop_loss: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    stop_loss_triggered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    take_profit_triggered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    entry_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    pnl_percent: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    market_price_at_entry: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    integrity_checks_passed: Mapped[int] = mapped_column(BigInteger, default=0)
    integrity_checks_total: Mapped[int] = mapped_column(BigInteger, default=0)
    integrity_failures: Mapped[list | None] = mapped_column(JSON, nullable=True)

    strategy_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    signal_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
