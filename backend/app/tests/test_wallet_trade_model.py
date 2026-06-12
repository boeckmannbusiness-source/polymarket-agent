import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, text

from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.repositories.wallet_trade_repository import WalletTradeRepository


BASE58_CHARS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _make_address() -> str:
    return "".join(chr(ord("A") + (i % 26)) for i in range(44))


def _make_mint() -> str:
    return BASE58_CHARS[:44]


def _make_tx() -> str:
    return BASE58_CHARS + BASE58_CHARS[:6]


def _make_block_time() -> datetime:
    return datetime(2026, 6, 1, 0, 0, 0)


@pytest.mark.asyncio
class TestWalletTradeModel:
    async def _create_wallet(self, db_session) -> SmartWallet:
        wallet = SmartWallet(
            wallet_address=_make_address(),
            source="helius",
            first_seen_at=_make_block_time(),
        )
        db_session.add(wallet)
        await db_session.commit()
        return wallet

    async def test_create_trade(self, db_session):
        wallet = await self._create_wallet(db_session)
        trade = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=5000.00,
            price_usd=142.50,
            block_time=_make_block_time(),
        )
        db_session.add(trade)
        await db_session.commit()

        assert trade.id is not None
        assert trade.side == "buy"

    async def test_tx_signature_unique(self, db_session):
        wallet = await self._create_wallet(db_session)
        tx = _make_tx()
        t1 = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=tx,
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )
        db_session.add(t1)
        await db_session.commit()

        t2 = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=tx,
            mint_address=_make_mint(),
            side="sell",
            size_usd=200.0,
            price_usd=55.0,
            block_time=_make_block_time(),
        )
        db_session.add(t2)
        with pytest.raises(Exception):
            await db_session.commit()
        await db_session.rollback()

    async def test_foreign_key_constraint(self, db_session):
        await db_session.execute(text("PRAGMA foreign_keys=ON"))
        fake_id = uuid.uuid4()
        trade = SolanaWalletTrade(
            wallet_id=fake_id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )
        db_session.add(trade)
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_optional_fields(self, db_session):
        wallet = await self._create_wallet(db_session)
        trade = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="sell",
            size_usd=2500.00,
            price_usd=155.00,
            block_time=_make_block_time(),
            token_symbol="SOL",
            slot=284195632,
        )
        db_session.add(trade)
        await db_session.commit()

        assert trade.token_symbol == "SOL"
        assert trade.slot == 284195632

    async def test_defaults(self, db_session):
        wallet = await self._create_wallet(db_session)
        trade = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )
        db_session.add(trade)
        await db_session.commit()

        assert trade.token_symbol is None
        assert trade.slot is None
        assert trade.created_at is not None

    async def test_cascade_delete(self, db_session):
        wallet = await self._create_wallet(db_session)
        trade = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )
        db_session.add(trade)
        await db_session.commit()
        trade_id = trade.id

        await db_session.delete(wallet)
        await db_session.commit()

        remaining = await db_session.execute(select(SolanaWalletTrade).where(SolanaWalletTrade.id == trade_id))
        assert remaining.scalar_one_or_none() is None


@pytest.mark.asyncio
class TestWalletTradeRepository:
    async def _create_wallet(self, db_session) -> SmartWallet:
        wallet = SmartWallet(
            wallet_address=_make_address(),
            source="helius",
            first_seen_at=_make_block_time(),
        )
        db_session.add(wallet)
        await db_session.commit()
        return wallet

    async def test_create_trade(self, db_session):
        wallet = await self._create_wallet(db_session)
        repo = WalletTradeRepository(db_session)
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=5000.00,
            price_usd=142.50,
            block_time=_make_block_time(),
            token_symbol="SOL",
            slot=284195632,
        )
        assert trade.id is not None
        assert trade.tx_signature is not None

    async def test_get_by_signature(self, db_session):
        wallet = await self._create_wallet(db_session)
        repo = WalletTradeRepository(db_session)
        tx = _make_tx()
        await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=tx,
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )

        found = await repo.get_by_signature(tx)
        assert found is not None
        assert found.tx_signature == tx

    async def test_get_by_signature_not_found(self, db_session):
        repo = WalletTradeRepository(db_session)
        result = await repo.get_by_signature("nonexistent")
        assert result is None

    async def test_list_for_wallet(self, db_session):
        wallet = await self._create_wallet(db_session)
        repo = WalletTradeRepository(db_session)
        for i in range(3):
            await repo.create_trade(
                wallet_id=wallet.id,
                tx_signature=_make_tx() + chr(ord("A") + i),
                mint_address=_make_mint(),
                side="buy",
                size_usd=100.0 * (i + 1),
                price_usd=50.0,
                block_time=_make_block_time(),
            )

        trades = await repo.list_for_wallet(wallet.id)
        assert len(trades) >= 3

    async def test_list_for_mint(self, db_session):
        wallet = await self._create_wallet(db_session)
        repo = WalletTradeRepository(db_session)
        mint = _make_mint()
        for i in range(2):
            await repo.create_trade(
                wallet_id=wallet.id,
                tx_signature=_make_tx() + chr(ord("Z") + i),
                mint_address=mint,
                side="buy",
                size_usd=100.0,
                price_usd=50.0,
                block_time=_make_block_time(),
            )

        trades = await repo.list_for_mint(mint)
        assert len(trades) >= 2

    async def test_get_by_id(self, db_session):
        wallet = await self._create_wallet(db_session)
        repo = WalletTradeRepository(db_session)
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_block_time(),
        )

        found = await repo.get_by_id(trade.id)
        assert found is not None
        assert found.id == trade.id
