import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BenchmarkPrice(Base):
    __tablename__ = "benchmark_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    benchmark_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
