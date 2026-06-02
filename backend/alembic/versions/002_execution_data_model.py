"""
Execution Data Model: exchange_orders and fills tables

Adds the ExchangeOrder and Fill models for the new execution hierarchy:
  Trade → ExchangeOrder → Fill

Revision ID: 002_execution_data_model
Revises: 001_trading_correctness_remediation
Create Date: 2026-06-02 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "002_execution_data_model"
down_revision: Union[str, None] = "001_trading_correctness_remediation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── exchange_orders table ──
    op.create_table(
        "exchange_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trade_id", sa.UUID(), sa.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_num", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("engine_type", sa.String(length=16), server_default="paper", nullable=False),
        sa.Column("exchange", sa.String(length=32), server_default="polymarket_clob", nullable=False),
        sa.Column("clob_order_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("clob_asset_id", sa.String(length=128), nullable=True),
        sa.Column("clob_signature", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("size", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("filled_size", sa.Numeric(precision=24, scale=8), server_default=sa.text("0"), nullable=False),
        sa.Column("filled_price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("fee", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("slippage", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("raw_request", postgresql.JSONB(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'partially_filled', 'filled', 'cancelled', 'failed')",
            name=op.f("ck_exchange_orders_status"),
        ),
        sa.CheckConstraint("side IN ('buy', 'sell')", name=op.f("ck_exchange_orders_side")),
        sa.CheckConstraint("outcome IN ('YES', 'NO')", name=op.f("ck_exchange_orders_outcome")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_id", "order_num", name=op.f("uq_exchange_orders_trade_order")),
    )
    op.create_index(op.f("ix_exchange_orders_trade_id"), "exchange_orders", ["trade_id"])
    op.create_index(op.f("ix_exchange_orders_clob_order_id"), "exchange_orders", ["clob_order_id"])
    op.create_index(op.f("ix_exchange_orders_status"), "exchange_orders", ["status"])
    op.create_index(op.f("ix_exchange_orders_engine_type"), "exchange_orders", ["engine_type"])

    # ── fills table ──
    op.create_table(
        "fills",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exchange_order_id", sa.UUID(), sa.ForeignKey("exchange_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trade_id", sa.UUID(), sa.ForeignKey("trades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_id", sa.UUID(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("fill_num", sa.Integer(), nullable=False),
        sa.Column("clob_fill_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("transaction_hash", sa.String(length=128), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("size", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("fee", sa.Numeric(precision=24, scale=8), server_default=sa.text("0"), nullable=False),
        sa.Column("maker_address", sa.String(length=64), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("side IN ('buy', 'sell')", name=op.f("ck_fills_side")),
        sa.CheckConstraint("outcome IN ('YES', 'NO')", name=op.f("ck_fills_outcome")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_order_id", "fill_num", name=op.f("uq_fills_exchange_order_fill")),
    )
    op.create_index(op.f("ix_fills_exchange_order_id"), "fills", ["exchange_order_id"])
    op.create_index(op.f("ix_fills_trade_id"), "fills", ["trade_id"])
    op.create_index(op.f("ix_fills_market_id"), "fills", ["market_id"])
    op.create_index(op.f("ix_fills_filled_at"), "fills", ["filled_at"])


def downgrade() -> None:
    op.drop_table("fills")
    op.drop_table("exchange_orders")
