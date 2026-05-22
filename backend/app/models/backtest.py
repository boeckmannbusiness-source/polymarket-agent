import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Integer, DateTime, Text, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    strategy_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_capital: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    final_capital: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    calmar_ratio: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    expectancy: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    total_pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("backtest_runs.id"), nullable=False)
    market_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("markets.id"), nullable=True)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    size: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    pnl: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)
    entry_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signal_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
