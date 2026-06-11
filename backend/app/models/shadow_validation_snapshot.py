import uuid
from datetime import datetime

from sqlalchemy import String, Integer, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ShadowValidationSnapshot(Base):
    __tablename__ = "shadow_validation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    market_data_count: Mapped[int] = mapped_column(Integer, default=0)
    wallet_trade_count: Mapped[int] = mapped_column(Integer, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    trade_request_count: Mapped[int] = mapped_column(Integer, default=0)
    shadow_decision_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_approved_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    shadow_approved_count: Mapped[int] = mapped_column(Integer, default=0)
    shadow_blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    unique_wallets: Mapped[int] = mapped_column(Integer, default=0)
    unique_markets: Mapped[int] = mapped_column(Integer, default=0)
    exception_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
