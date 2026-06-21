import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from sqlalchemy import Index

from app.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("signals.id"), nullable=True)
    trade_type: Mapped[str] = mapped_column(String(16), nullable=False, default="paper")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── PERSISTENCE COMPATIBILITY ──
    compat_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compat_condition_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    order_type: Mapped[str] = mapped_column(String(16), nullable=False, default="market")

    # ── LEGACY FIELDS ──
    # New execution logic must use: Trade → ExchangeOrder → Fill
    # These fields remain for backward compatibility with PaperEngine
    # and will be migrated in a later phase.

    size: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    # LEGACY: use ExchangeOrder.filled_size
    filled_size: Mapped[float] = mapped_column(Numeric(24, 8), default=0)
    # LEGACY: use ExchangeOrder.filled_price
    filled_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    # LEGACY: use ExchangeOrder.slippage
    slippage: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    # LEGACY: use ExchangeOrder.fee + Fill.fee
    fee: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    # LEGACY: Fill-based PnL computation
    pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    # LEGACY: Fill-based PnL computation
    pnl_percent: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_check_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Relationships ──
    orders: Mapped[list["ExchangeOrder"]] = relationship(
        back_populates="trade", cascade="all, delete-orphan",
    )
    fills: Mapped[list["Fill"]] = relationship(
        back_populates="trade",
    )


Index(
    "ix_trades_unique_open_per_market_outcome",
    Trade.market_id,
    Trade.outcome,
    unique=True,
    postgresql_where=Trade.status.in_(["open", "pending"]),
    sqlite_where=Trade.status.in_(["open", "pending"]),
)
