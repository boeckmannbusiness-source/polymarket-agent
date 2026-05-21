import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Boolean, DateTime, Text, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    implied_probability: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    estimated_probability: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
