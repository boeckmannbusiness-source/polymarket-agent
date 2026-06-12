import uuid
from datetime import datetime

import pytest
from sqlalchemy import select, func, text

from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.models.research_trade import ResearchTrade
from app.repositories.research_trade_repository import ResearchTradeRepository


BASE58_CHARS = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _make_address() -> str:
    return "".join(chr(ord("A") + (i % 26)) for i in range(44))


def _make_mint() -> str:
    return BASE58_CHARS[:44]


def _make_tx() -> str:
    return BASE58_CHARS + BASE58_CHARS[:6]


def _make_time() -> datetime:
    return datetime(2026, 6, 1, 0, 0, 0)


@pytest.mark.asyncio
class TestResearchTradeModel:
    async def _create_wallet_and_trade(self, db_session):
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=_make_time())
        db_session.add(wallet)
        await db_session.commit()

        wt = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_time(),
        )
        db_session.add(wt)
        await db_session.commit()
        return wallet, wt

    async def test_create_research_trade(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        rt = ResearchTrade(
            wallet_trade_id=wt.id,
            strategy="smart_wallet_follow",
            entry_price=142.50,
            opened_at=_make_time(),
        )
        db_session.add(rt)
        await db_session.commit()

        assert rt.id is not None
        assert rt.status == "open"
        assert rt.strategy == "smart_wallet_follow"

    async def test_default_status(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        rt = ResearchTrade(
            wallet_trade_id=wt.id,
            strategy="test_strategy",
            entry_price=100.0,
            opened_at=_make_time(),
        )
        db_session.add(rt)
        await db_session.commit()

        assert rt.status == "open"

    async def test_optional_fields(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        rt = ResearchTrade(
            signal_id="sig_test123",
            wallet_trade_id=wt.id,
            strategy="smart_wallet_follow",
            confidence=0.75,
            entry_price=142.50,
            opened_at=_make_time(),
        )
        db_session.add(rt)
        await db_session.commit()

        assert rt.signal_id == "sig_test123"
        assert rt.confidence == 0.75
        assert rt.exit_price is None
        assert rt.pnl_usd is None
        assert rt.closed_at is None

    async def test_close_trade(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        rt = ResearchTrade(
            wallet_trade_id=wt.id,
            strategy="test",
            entry_price=100.0,
            opened_at=_make_time(),
        )
        db_session.add(rt)
        await db_session.commit()

        now = datetime(2026, 6, 2, 0, 0, 0)
        rt.exit_price = 150.0
        rt.pnl_usd = 48.5
        rt.status = "closed"
        rt.closed_at = now
        await db_session.commit()

        assert rt.status == "closed"
        assert rt.exit_price == 150.0
        assert rt.pnl_usd == 48.5

    async def test_strategy_index(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        db_session.add(ResearchTrade(wallet_trade_id=wt.id, strategy="strat_a", entry_price=100.0, opened_at=_make_time()))
        await db_session.commit()

        result = await db_session.execute(
            select(ResearchTrade).where(ResearchTrade.strategy == "strat_a"),
        )
        assert result.scalar_one_or_none() is not None

    async def test_status_index(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        db_session.add(ResearchTrade(wallet_trade_id=wt.id, strategy="test", entry_price=100.0, opened_at=_make_time()))
        await db_session.commit()

        result = await db_session.execute(
            select(ResearchTrade).where(ResearchTrade.status == "open"),
        )
        assert result.scalar_one_or_none() is not None

    async def test_fk_set_null_on_delete(self, db_session):
        await db_session.execute(text("PRAGMA foreign_keys=ON"))
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=_make_time())
        db_session.add(wallet)
        await db_session.commit()

        wt = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_time(),
        )
        db_session.add(wt)
        await db_session.commit()

        rt = ResearchTrade(
            wallet_trade_id=wt.id,
            strategy="test",
            entry_price=100.0,
            opened_at=_make_time(),
        )
        db_session.add(rt)
        await db_session.commit()

        rt_id = rt.id
        wt_id = wt.id

        await db_session.delete(wt)
        await db_session.commit()

        db_session.expire_all()

        remaining = await db_session.execute(select(ResearchTrade).where(ResearchTrade.id == rt_id))
        rt_check = remaining.scalar_one_or_none()
        assert rt_check is not None
        assert rt_check.wallet_trade_id is None


@pytest.mark.asyncio
class TestResearchTradeRepository:
    async def _create_wallet_and_trade(self, db_session):
        wallet = SmartWallet(wallet_address=_make_address(), source="helius", first_seen_at=_make_time())
        db_session.add(wallet)
        await db_session.commit()

        wt = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=_make_tx(),
            mint_address=_make_mint(),
            side="buy",
            size_usd=100.0,
            price_usd=50.0,
            block_time=_make_time(),
        )
        db_session.add(wt)
        await db_session.commit()
        return wallet, wt

    async def test_create_trade(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        rt = await repo.create_trade(
            strategy="smart_wallet_follow",
            entry_price=142.50,
            opened_at=_make_time(),
            wallet_trade_id=wt.id,
            confidence=0.75,
        )
        assert rt.id is not None
        assert rt.status == "open"
        assert rt.confidence == 0.75

    async def test_close_trade(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        rt = await repo.create_trade(
            strategy="test",
            entry_price=100.0,
            opened_at=_make_time(),
            wallet_trade_id=wt.id,
        )

        closed = await repo.close_trade(rt.id, exit_price=150.0, pnl_usd=48.5)
        assert closed is not None
        assert closed.status == "closed"
        assert closed.exit_price == 150.0
        assert closed.pnl_usd == 48.5

    async def test_list_open_positions(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        for i in range(2):
            await repo.create_trade(
                strategy="test",
                entry_price=100.0 * (i + 1),
                opened_at=_make_time(),
                wallet_trade_id=wt.id,
            )

        open_positions = await repo.list_open_positions()
        assert len(open_positions) >= 2

    async def test_list_open_by_strategy(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        await repo.create_trade(strategy="strat_a", entry_price=100.0, opened_at=_make_time(), wallet_trade_id=wt.id)
        await repo.create_trade(strategy="strat_b", entry_price=200.0, opened_at=_make_time(), wallet_trade_id=wt.id)

        strat_a = await repo.list_open_positions(strategy="strat_a")
        assert len(strat_a) == 1
        assert strat_a[0].strategy == "strat_a"

    async def test_list_by_strategy(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        await repo.create_trade(strategy="strat_a", entry_price=100.0, opened_at=_make_time(), wallet_trade_id=wt.id)
        await repo.create_trade(strategy="strat_a", entry_price=200.0, opened_at=_make_time(), wallet_trade_id=wt.id)

        trades = await repo.list_by_strategy("strat_a")
        assert len(trades) == 2

    async def test_close_nonexistent(self, db_session):
        repo = ResearchTradeRepository(db_session)
        result = await repo.close_trade(uuid.uuid4(), exit_price=100.0, pnl_usd=0.0)
        assert result is None

    async def test_count_open(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        for i in range(3):
            await repo.create_trade(strategy="test", entry_price=100.0, opened_at=_make_time(), wallet_trade_id=wt.id)

        count = await repo.count_open()
        assert count >= 3

    async def test_get_by_id(self, db_session):
        _, wt = await self._create_wallet_and_trade(db_session)
        repo = ResearchTradeRepository(db_session)
        rt = await repo.create_trade(strategy="test", entry_price=100.0, opened_at=_make_time(), wallet_trade_id=wt.id)

        found = await repo.get_by_id(rt.id)
        assert found is not None
        assert found.id == rt.id

    async def test_get_by_id_not_found(self, db_session):
        repo = ResearchTradeRepository(db_session)
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None
