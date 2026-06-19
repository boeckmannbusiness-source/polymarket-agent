"""
Generic Execution Models Migration

Adds Solana-compatible fields to execution models:
- ExchangeOrder: external_id, asset_id, input_mint, output_mint (outcome → nullable)
- Fill: external_id (outcome → nullable)
- Trade: asset_in, asset_out (outcome → nullable)

All legacy Polymarket fields (clob_*) preserved.
No destructive changes.

Revision ID: 007_generic_execution_models
Revises: 006_create_shadow_positions
Create Date: 2026-06-19 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "007_generic_execution_models"
down_revision: Union[str, None] = "006_create_shadow_positions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── exchange_orders ──────────────────────────────────────

    # Add new Solana-compatible fields
    op.add_column("exchange_orders", sa.Column("external_id", sa.String(length=128), nullable=True, unique=True))
    op.add_column("exchange_orders", sa.Column("asset_id", sa.String(length=128), nullable=True))
    op.add_column("exchange_orders", sa.Column("input_mint", sa.String(length=64), nullable=True))
    op.add_column("exchange_orders", sa.Column("output_mint", sa.String(length=64), nullable=True))

    # Relax outcome constraint: drop CHECK, make nullable
    op.drop_constraint("ck_exchange_orders_outcome", "exchange_orders")
    op.alter_column("exchange_orders", "outcome", existing_type=sa.String(16), nullable=True)

    # Add index for new lookup path
    op.create_index(op.f("ix_exchange_orders_external_id"), "exchange_orders", ["external_id"])
    op.create_index(op.f("ix_exchange_orders_asset_id"), "exchange_orders", ["asset_id"])

    # ── fills ─────────────────────────────────────────────────

    # Add Solana-compatible external_id
    op.add_column("fills", sa.Column("external_id", sa.String(length=128), nullable=True, unique=True))

    # Relax outcome constraint
    op.drop_constraint("ck_fills_outcome", "fills")
    op.alter_column("fills", "outcome", existing_type=sa.String(16), nullable=True)

    # Add index for new lookup path
    op.create_index(op.f("ix_fills_external_id"), "fills", ["external_id"])

    # ── trades ────────────────────────────────────────────────

    # Add Solana-compatible fields
    op.add_column("trades", sa.Column("asset_in", sa.String(length=64), nullable=True))
    op.add_column("trades", sa.Column("asset_out", sa.String(length=64), nullable=True))

    # Make outcome nullable (no CHECK constraint to drop on trades)
    op.alter_column("trades", "outcome", existing_type=sa.String(64), nullable=True)


def downgrade() -> None:
    # ── trades ────────────────────────────────────────────────
    op.alter_column("trades", "outcome", existing_type=sa.String(64), nullable=False)
    op.drop_column("trades", "asset_out")
    op.drop_column("trades", "asset_in")

    # ── fills ─────────────────────────────────────────────────
    op.drop_index(op.f("ix_fills_external_id"), table_name="fills")
    op.drop_column("fills", "external_id")
    op.alter_column("fills", "outcome", existing_type=sa.String(16), nullable=False)
    op.create_check_constraint("ck_fills_outcome", "fills", "outcome IN ('YES', 'NO')")

    # ── exchange_orders ───────────────────────────────────────
    op.drop_index(op.f("ix_exchange_orders_asset_id"), table_name="exchange_orders")
    op.drop_index(op.f("ix_exchange_orders_external_id"), table_name="exchange_orders")
    op.alter_column("exchange_orders", "outcome", existing_type=sa.String(16), nullable=False)
    op.create_check_constraint("ck_exchange_orders_outcome", "exchange_orders", "outcome IN ('YES', 'NO')")
    op.drop_column("exchange_orders", "output_mint")
    op.drop_column("exchange_orders", "input_mint")
    op.drop_column("exchange_orders", "asset_id")
    op.drop_column("exchange_orders", "external_id")
