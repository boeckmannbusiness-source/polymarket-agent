"""
Create shadow_positions table for T3-V1 Shadow Portfolio Service.

Tracks simulated positions derived from Solana research signals
with TP/SL evaluation for shadow portfolio tracking.

Revision ID: 006_create_shadow_positions
Revises: 005_create_research_hypotheses
Create Date: 2026-06-15 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006_create_shadow_positions"
down_revision: Union[str, None] = "005_create_research_hypotheses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_positions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("research_trade_id", sa.UUID(), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("entry_price", sa.Numeric(24, 8), nullable=False),
        sa.Column("current_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("exit_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("size_usd", sa.Numeric(24, 8), nullable=False),
        sa.Column("tp_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("sl_price", sa.Numeric(24, 8), nullable=True),
        sa.Column("gross_pnl_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("net_pnl_usd", sa.Numeric(24, 8), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["research_trade_id"],
            ["research_trades.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("research_trade_id", name="uq_shadow_position_research_trade"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_shadow_position_status"),
    )
    op.create_index(
        op.f("ix_shadow_positions_strategy"),
        "shadow_positions",
        ["strategy"],
    )
    op.create_index(
        op.f("ix_shadow_positions_status"),
        "shadow_positions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_constraint("ck_shadow_position_status", "shadow_positions")
    op.drop_index(op.f("ix_shadow_positions_status"), table_name="shadow_positions")
    op.drop_index(op.f("ix_shadow_positions_strategy"), table_name="shadow_positions")
    op.drop_constraint("uq_shadow_position_research_trade", "shadow_positions")
    op.drop_table("shadow_positions")
