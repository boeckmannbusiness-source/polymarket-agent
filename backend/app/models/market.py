import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, BigInteger, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    condition_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcomes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    volume: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    liquidity: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    clob_token_ids: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_source: Mapped[str | None] = mapped_column(String(256), nullable=True)

    events: Mapped[list["MarketEvent"]] = relationship(back_populates="market", lazy="dynamic")


class MarketEvent(Base):
    __tablename__ = "market_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    block_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    transaction_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    maker_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    taker_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    side: Mapped[str | None] = mapped_column(String(16), nullable=True)
    size: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    fee: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    market: Mapped["Market"] = relationship(back_populates="events")
