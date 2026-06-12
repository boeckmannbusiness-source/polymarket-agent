"""
Create Solana Domain Models: smart_wallets, solana_wallet_trades, research_trades

Adds the SmartWallet, WalletTrade, and ResearchTrade models for the
Solana Smart Wallet tracking system.

Revision ID: 004_create_solana_domain_models
Revises: 003_widen_market_id_v128
Create Date: 2026-06-12 00:00:00.000000

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "004_create_solana_domain_models"
down_revision: Union[str, None] = "003_widen_market_id_v128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── smart_wallets ────────────────────────────────────────
    op.create_table(
        "smart_wallets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_address", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'helius'")),
        sa.Column("score", sa.Numeric(precision=12, scale=6), nullable=False, server_default=sa.text("0.0")),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("win_rate", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("pnl_usd", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_address", name=op.f("uq_smart_wallets_wallet_address")),
    )
    op.create_index(op.f("ix_smart_wallets_wallet_address"), "smart_wallets", ["wallet_address"])
    op.create_index(op.f("ix_smart_wallets_score"), "smart_wallets", ["score"])
    op.create_index(op.f("ix_smart_wallets_is_active"), "smart_wallets", ["is_active"])

    # ── solana_wallet_trades ────────────────────────────────
    op.create_table(
        "solana_wallet_trades",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("tx_signature", sa.String(length=128), nullable=False),
        sa.Column("mint_address", sa.String(length=64), nullable=False),
        sa.Column("token_symbol", sa.String(length=16), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("size_usd", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("price_usd", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("slot", sa.BigInteger(), nullable=True),
        sa.Column("block_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["smart_wallets.id"], name=op.f("fk_solana_wallet_trades_wallet_id"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tx_signature", name=op.f("uq_solana_wallet_trades_tx_signature")),
    )
    op.create_index(op.f("ix_solana_wallet_trades_wallet_id"), "solana_wallet_trades", ["wallet_id"])
    op.create_index(op.f("ix_solana_wallet_trades_mint_address"), "solana_wallet_trades", ["mint_address"])
    op.create_index(op.f("ix_solana_wallet_trades_block_time"), "solana_wallet_trades", ["block_time"])

    # ── research_trades ──────────────────────────────────────
    op.create_table(
        "research_trades",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("signal_id", sa.String(length=64), nullable=True),
        sa.Column("wallet_trade_id", sa.UUID(), nullable=True),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=8, scale=6), nullable=True),
        sa.Column("entry_price", sa.Numeric(precision=24, scale=8), nullable=False),
        sa.Column("exit_price", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("pnl_usd", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["wallet_trade_id"], ["solana_wallet_trades.id"], name=op.f("fk_research_trades_wallet_trade_id"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_research_trades_signal_id"), "research_trades", ["signal_id"])
    op.create_index(op.f("ix_research_trades_strategy"), "research_trades", ["strategy"])
    op.create_index(op.f("ix_research_trades_status"), "research_trades", ["status"])


def downgrade() -> None:
    op.drop_table("research_trades")
    op.drop_table("solana_wallet_trades")
    op.drop_table("smart_wallets")
