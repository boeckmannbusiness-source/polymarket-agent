import uuid
from datetime import datetime

import pytest
from sqlalchemy import select

from app.models.smart_wallet import SmartWallet
from app.repositories.smart_wallet_repository import SmartWalletRepository


def _make_address() -> str:
    return "".join(chr(ord("A") + (i % 26)) for i in range(44))


@pytest.mark.asyncio
class TestSmartWalletModel:
    async def test_create_wallet(self, db_session):
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = SmartWallet(
            wallet_address=_make_address(),
            source="helius",
            first_seen_at=now,
        )
        db_session.add(wallet)
        await db_session.commit()
        assert wallet.id is not None
        assert wallet.score == 0.0
        assert wallet.total_trades == 0
        assert wallet.is_active is True

    async def test_wallet_address_unique(self, db_session):
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        w1 = SmartWallet(wallet_address=addr, source="helius", first_seen_at=now)
        db_session.add(w1)
        await db_session.commit()

        w2 = SmartWallet(wallet_address=addr, source="manual", first_seen_at=now)
        db_session.add(w2)
        with pytest.raises(Exception):
            await db_session.commit()

    async def test_wallet_address_indexed(self, db_session):
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=now)
        db_session.add(wallet)
        await db_session.commit()

        result = await db_session.execute(
            select(SmartWallet).where(SmartWallet.wallet_address == wallet.wallet_address),
        )
        assert result.scalar_one_or_none() is not None

    async def test_default_values(self, db_session):
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=now)
        db_session.add(wallet)
        await db_session.commit()

        assert wallet.score == 0.0
        assert wallet.total_trades == 0
        assert wallet.is_active is True
        assert wallet.label is None
        assert wallet.win_rate is None
        assert wallet.pnl_usd is None
        assert wallet.last_seen_at is None

    async def test_optional_fields(self, db_session):
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = SmartWallet(
            wallet_address=_make_address(),
            source="manual",
            label="test wallet",
            score=0.85,
            total_trades=42,
            win_rate=0.61,
            pnl_usd=1500.50,
            is_active=False,
            first_seen_at=now,
            last_seen_at=now,
        )
        db_session.add(wallet)
        await db_session.commit()

        assert wallet.label == "test wallet"
        assert wallet.score == 0.85
        assert wallet.total_trades == 42
        assert wallet.win_rate == 0.61
        assert wallet.pnl_usd == 1500.50
        assert wallet.is_active is False

    async def test_timestamps_set_on_create(self, db_session):
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=now)
        db_session.add(wallet)
        await db_session.commit()

        assert wallet.created_at is not None
        assert wallet.updated_at is not None


@pytest.mark.asyncio
class TestSmartWalletRepository:
    async def test_create_wallet(self, db_session):
        repo = SmartWalletRepository(db_session)
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = await repo.create_wallet(
            wallet_address=_make_address(),
            source="helius",
            first_seen_at=now,
        )
        assert wallet.id is not None
        assert wallet.wallet_address is not None

    async def test_get_by_address(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        await repo.create_wallet(wallet_address=addr, source="helius", first_seen_at=now)

        found = await repo.get_by_address(addr)
        assert found is not None
        assert found.wallet_address == addr

    async def test_get_by_address_not_found(self, db_session):
        repo = SmartWalletRepository(db_session)
        result = await repo.get_by_address("nonexistent")
        assert result is None

    async def test_update_metrics(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = await repo.create_wallet(wallet_address=addr, source="helius", first_seen_at=now)

        updated = await repo.update_metrics(wallet.id, total_trades=10, win_rate=0.5, pnl_usd=100.0, score=0.75)
        assert updated is not None
        assert updated.total_trades == 10
        assert updated.win_rate == 0.5
        assert updated.pnl_usd == 100.0
        assert updated.score == 0.75

    async def test_list_active(self, db_session):
        repo = SmartWalletRepository(db_session)
        now = datetime(2026, 6, 1, 0, 0, 0)
        await repo.create_wallet(wallet_address=_make_address() + "A", source="helius", first_seen_at=now)
        await repo.create_wallet(wallet_address=_make_address() + "B", source="helius", first_seen_at=now)

        active = await repo.list_active()
        assert len(active) >= 2

    async def test_upsert_new_wallet(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        wallet = await repo.upsert_wallet(wallet_address=addr, source="helius", label="upserted")
        assert wallet is not None
        assert wallet.label == "upserted"

    async def test_upsert_existing_wallet(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        w1 = await repo.create_wallet(wallet_address=addr, source="helius", first_seen_at=now)

        w2 = await repo.upsert_wallet(wallet_address=addr, source="helius", score=0.95)
        assert w2.id == w1.id
        assert w2.score == 0.95

    async def test_get_by_id(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = await repo.create_wallet(wallet_address=addr, source="helius", first_seen_at=now)

        found = await repo.get_by_id(wallet.id)
        assert found is not None
        assert found.id == wallet.id

    async def test_update_metrics_no_changes(self, db_session):
        repo = SmartWalletRepository(db_session)
        addr = _make_address()
        now = datetime(2026, 6, 1, 0, 0, 0)
        wallet = await repo.create_wallet(wallet_address=addr, source="helius", first_seen_at=now)

        updated = await repo.update_metrics(wallet.id)
        assert updated is not None
        assert updated.score == 0.0
