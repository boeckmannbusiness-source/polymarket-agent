import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class SolanaWalletTrade(Base):
    __tablename__ = "solana_wallet_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("smart_wallets.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    tx_signature: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    mint_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    size_usd: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    price_usd: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    slot: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    block_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wallet: Mapped["SmartWallet"] = relationship(back_populates="wallet_trades")
