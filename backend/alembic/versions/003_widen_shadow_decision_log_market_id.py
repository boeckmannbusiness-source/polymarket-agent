"""Widen shadow_decision_log.market_id from VARCHAR(64) to VARCHAR(128)

Condition IDs from Polygon are 66-char hex strings (0x + 64 hex chars),
which exceeded the original 64-char limit causing silent StringDataRightTruncationError.

Revision ID: 003_widen_shadow_decision_log_market_id
Revises: 002_execution_data_model
Create Date: 2026-06-10 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "003_widen_market_id_v128"
down_revision: Union[str, None] = "002_execution_data_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "shadow_decision_log",
        "market_id",
        type_=sa.String(128),
        existing_type=sa.String(64),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "shadow_decision_log",
        "market_id",
        type_=sa.String(64),
        existing_type=sa.String(128),
        nullable=True,
    )
