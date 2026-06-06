import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ShadowDecisionLog(Base):
    __tablename__ = "shadow_decision_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    market_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    strategy_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    signal_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    regime_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimization_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    stability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    drift_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    safety_gate_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
