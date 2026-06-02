import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Integer, DateTime, Text, CheckConstraint, UniqueConstraint, Index
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Fill(Base):
    __tablename__ = "fills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exchange_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("markets.id"),
        nullable=False,
    )
    fill_num: Mapped[int] = mapped_column(Integer, nullable=False)

    clob_fill_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    side: Mapped[str] = mapped_column(String(8), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))

    maker_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    exchange_order: Mapped["ExchangeOrder"] = relationship(back_populates="fills")
    trade: Mapped["Trade"] = relationship(back_populates="fills")

    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="ck_fills_side"),
        CheckConstraint("outcome IN ('YES', 'NO')", name="ck_fills_outcome"),
        UniqueConstraint("exchange_order_id", "fill_num", name="uq_fills_exchange_order_fill"),
        Index("ix_fills_market_id", "market_id"),
        Index("ix_fills_filled_at", "filled_at"),
    )
