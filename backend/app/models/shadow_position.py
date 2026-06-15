import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


_CLOSED_REASONS = ("take_profit", "stop_loss", "timeout", "manual")


class ShadowPosition(Base):
    # ARCHITECTURE RULE:
    # Validation analytics only.
    # Never participate in:
    #   scoring
    #   ranking
    #   confidence
    #   hypothesis generation
    __tablename__ = "shadow_positions"

    __table_args__ = (
        UniqueConstraint("research_trade_id", name="uq_shadow_position_research_trade"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_shadow_position_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("research_trades.id", ondelete="SET NULL"), nullable=True,
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    size_usd: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    tp_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    sl_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    gross_pnl_usd: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    net_pnl_usd: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
