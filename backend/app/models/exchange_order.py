import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Integer, DateTime, Text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ExchangeOrder(Base):
    __tablename__ = "exchange_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_num: Mapped[int] = mapped_column(Integer, default=1)

    engine_type: Mapped[str] = mapped_column(String(16), default="paper")
    exchange: Mapped[str] = mapped_column(String(32), default="polymarket_clob")

    clob_order_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    clob_asset_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    clob_signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="pending")
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    size: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)

    filled_size: Mapped[Decimal] = mapped_column(Numeric(24, 8), default=Decimal("0"))
    filled_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    slippage: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trade: Mapped["Trade"] = relationship(back_populates="orders")
    fills: Mapped[list["Fill"]] = relationship(back_populates="exchange_order", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'submitted', 'partially_filled', 'filled', 'cancelled', 'failed')",
            name="ck_exchange_orders_status",
        ),
        CheckConstraint("side IN ('buy', 'sell')", name="ck_exchange_orders_side"),
        CheckConstraint("outcome IN ('YES', 'NO')", name="ck_exchange_orders_outcome"),
        UniqueConstraint("trade_id", "order_num", name="uq_exchange_orders_trade_order"),
    )
