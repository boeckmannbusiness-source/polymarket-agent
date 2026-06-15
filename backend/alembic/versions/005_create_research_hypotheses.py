"""
Create research_hypotheses table for T3-04 Hypothesis Generator.

Adds the ResearchHypothesis model used to store generated hypotheses
about wallet behavior patterns with 7-day TTL.

Revision ID: 005_create_research_hypotheses
Revises: 004_create_solana_domain_models
Create Date: 2026-06-14 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005_create_research_hypotheses"
down_revision: Union[str, None] = "004_create_solana_domain_models"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_hypotheses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("hypothesis_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("score_1h", sa.Float(), nullable=True),
        sa.Column("score_24h", sa.Float(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("supporting_signals", postgresql.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_research_hypotheses_wallet_address"),
        "research_hypotheses",
        ["wallet_address"],
    )
    op.create_index(
        op.f("ix_research_hypotheses_expires_at"),
        "research_hypotheses",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_research_hypotheses_expires_at"), table_name="research_hypotheses")
    op.drop_index(op.f("ix_research_hypotheses_wallet_address"), table_name="research_hypotheses")
    op.drop_table("research_hypotheses")
