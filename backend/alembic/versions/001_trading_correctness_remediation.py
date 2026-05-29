"""
Trading Correctness Remediation Migration

Revision ID: 001_trading_correctness_remediation
Revises: None
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_trading_correctness_remediation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TC8: Add partial unique index for duplicate open trade prevention
    op.create_index(
        op.f("ix_trades_unique_open_per_market_outcome"),
        "trades",
        ["market_id", "outcome"],
        unique=False,
        postgresql_where=sa.text("status IN ('open', 'pending')"),
        sqlite_where=sa.text("status IN ('open', 'pending')"),
    )

    # TC12: Create strategy_allocation_states table
    op.create_table(
        "strategy_allocation_states",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("strategy_name", sa.String(length=64), nullable=False),
        sa.Column("allocated_capital", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_name", name=op.f("uq_strategy_allocation_states_strategy_name")),
    )

    # TC3: Add signal_eval_missing_entry_price metric
    op.execute(
        """
        INSERT INTO pipeline_metrics (metric_name, metric_value, created_at)
        VALUES ('signal_eval_missing_entry_price_total', 0, NOW())
        ON CONFLICT (metric_name) DO NOTHING
        """
    )

    # TC9: Add pending_trade_timeout_total metric
    op.execute(
        """
        INSERT INTO pipeline_metrics (metric_name, metric_value, created_at)
        VALUES ('pending_trade_timeout_total', 0, NOW())
        ON CONFLICT (metric_name) DO NOTHING
        """
    )


def downgrade() -> None:
    # TC12: Drop strategy_allocation_states table
    op.drop_table("strategy_allocation_states")

    # TC8: Drop partial unique index
    op.drop_index(op.f("ix_trades_unique_open_per_market_outcome"), table_name="trades")
