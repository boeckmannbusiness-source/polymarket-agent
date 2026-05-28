import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, Integer, Numeric
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SafetyState(Base):
    __tablename__ = "safety_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kill_switch_active: Mapped[bool] = mapped_column(Boolean, default=False)
    circuit_breaker_active: Mapped[bool] = mapped_column(Boolean, default=False)
    circuit_breaker_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quarantined_strategies: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    daily_pnl: Mapped[float] = mapped_column(Numeric(24, 8), default=0.0)
    checks_passed: Mapped[int] = mapped_column(Integer, default=0)
    checks_failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
