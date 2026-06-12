import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Integer, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class SmartWallet(Base):
    __tablename__ = "smart_wallets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    wallet_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="helius")
    score: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0.0)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    pnl_usd: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    wallet_trades: Mapped[list["SolanaWalletTrade"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan",
    )
