import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class TradeAttribution(Base):
    __tablename__ = "trade_attributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_outcome_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signal_outcomes.id"), nullable=False, index=True, unique=True
    )
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    entry_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    entry_momentum_1h: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    entry_volatility_1h: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    entry_spread_ratio: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    entry_volume_5m: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)
    entry_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_archetype: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_whale_size: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)

    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    exit_momentum_1h: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    exit_volatility_1h: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    exit_spread_ratio: Mapped[float | None] = mapped_column(Numeric(16, 8), nullable=True)
    exit_volume_5m: Mapped[float | None] = mapped_column(Numeric(24, 4), nullable=True)

    total_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    momentum_contribution: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    whale_contribution: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    spread_contribution: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    volatility_contribution: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    liquidity_contribution: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    residual: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    checkpoint_attributions: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    holding_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
