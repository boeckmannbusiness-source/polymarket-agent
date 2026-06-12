import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class ResearchTrade(Base):
    __tablename__ = "research_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    wallet_trade_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("solana_wallet_trades.id", ondelete="SET NULL"), nullable=True,
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    entry_price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wallet_trade: Mapped["SolanaWalletTrade | None"] = relationship()
