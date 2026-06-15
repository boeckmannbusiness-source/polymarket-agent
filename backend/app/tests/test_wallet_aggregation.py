import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade as WalletTrade
from app.repositories.wallet_trade_repository import WalletTradeRepository


@pytest.mark.asyncio
class TestWalletAggregation:
    async def _seed_wallet_with_trades(
        self, db: AsyncSession, wallet_address: str, trades: list[dict],
    ) -> SmartWallet:
        wallet = SmartWallet(
            wallet_address=wallet_address,
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        db.add(wallet)
        await db.flush()

        for t in trades:
            trade = WalletTrade(
                wallet_id=wallet.id,
                tx_signature=str(uuid.uuid4()),
                mint_address=t.get("mint", "mint1"),
                side=t.get("side", "buy"),
                size_usd=t.get("size", 100.0),
                price_usd=t.get("price", 1.0),
                block_time=t.get("block_time", datetime.now(timezone.utc)),
            )
            db.add(trade)
        await db.commit()
        return wallet

    async def test_aggregation_counts_1h_trades(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_a", [
            {"block_time": now - timedelta(minutes=30)},
            {"block_time": now - timedelta(hours=2)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert len(results) == 1
        assert results[0]["trades_1h"] == 1
        assert results[0]["trades_24h"] == 2

    async def test_aggregation_counts_24h_trades(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_b", [
            {"block_time": now - timedelta(hours=6)},
            {"block_time": now - timedelta(hours=12)},
            {"block_time": now - timedelta(hours=48)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert len(results) == 1
        assert results[0]["trades_24h"] == 2
        assert results[0]["trades_7d"] == 3

    async def test_token_diversity(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_c", [
            {"mint": "mint_a", "block_time": now - timedelta(hours=1)},
            {"mint": "mint_b", "block_time": now - timedelta(hours=2)},
            {"mint": "mint_a", "block_time": now - timedelta(hours=3)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert results[0]["token_diversity"] == 2

    async def test_active_days_7d(self, db_session: AsyncSession):
        base = datetime(2026, 6, 14, 12, 0, 0, tzinfo=timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_d", [
            {"block_time": base - timedelta(hours=2)},
            {"block_time": base - timedelta(hours=26)},
            {"block_time": base - timedelta(hours=50)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert results[0]["active_days_7d"] == 3

    async def test_volume_proxy(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_e", [
            {"size": 500.0, "block_time": now - timedelta(hours=1)},
            {"size": 1500.0, "block_time": now - timedelta(hours=2)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert results[0]["volume_proxy"] == pytest.approx(2000.0)

    async def test_last_trade_at(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_f", [
            {"block_time": now - timedelta(hours=5)},
            {"block_time": now - timedelta(hours=3)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        expected = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H")
        assert expected in results[0]["last_trade_at"]

    async def test_volume_proxy_excludes_unenriched_trades(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_une", [
            {"size": 1000.0, "price": 0.0, "block_time": now - timedelta(hours=1)},
            {"size": 500.0, "price": 2.0, "block_time": now - timedelta(hours=2)},
        ])
        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert results[0]["volume_proxy"] == pytest.approx(500.0)

    async def test_multiple_wallets(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_x", [
            {"block_time": now - timedelta(hours=1)},
        ])
        w2 = SmartWallet(
            wallet_address="wallet_y", source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(w2)
        await db_session.flush()
        t = WalletTrade(
            wallet_id=w2.id, tx_signature=str(uuid.uuid4()),
            mint_address="mint1", side="buy", size_usd=50.0, price_usd=1.0,
            block_time=now - timedelta(hours=1),
        )
        db_session.add(t)
        await db_session.commit()

        repo = WalletTradeRepository(db_session)
        results = await repo.aggregate_wallet_metrics()
        assert len(results) == 2
        addresses = {r["wallet_address"] for r in results}
        assert addresses == {"wallet_x", "wallet_y"}

    async def test_replay_safety(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        await self._seed_wallet_with_trades(db_session, "wallet_r", [
            {"size": 100.0, "block_time": now - timedelta(hours=1)},
        ])
        repo = WalletTradeRepository(db_session)
        r1 = await repo.aggregate_wallet_metrics()
        r2 = await repo.aggregate_wallet_metrics()
        assert len(r1) == len(r2)
        assert r1[0]["trades_24h"] == r2[0]["trades_24h"]
        assert r1[0]["volume_proxy"] == r2[0]["volume_proxy"]

    async def test_no_duplicate_aggregation(self, db_session: AsyncSession):
        now = datetime.now(timezone.utc)
        wallet = await self._seed_wallet_with_trades(db_session, "wallet_n", [
            {"size": 100.0, "block_time": now - timedelta(hours=1)},
        ])
        repo = WalletTradeRepository(db_session)
        r1 = await repo.aggregate_wallet_metrics()
        assert len(r1) == 1
        t2 = WalletTrade(
            wallet_id=wallet.id, tx_signature=str(uuid.uuid4()),
            mint_address="mint1", side="buy", size_usd=200.0, price_usd=1.0,
            block_time=now - timedelta(hours=2),
        )
        db_session.add(t2)
        await db_session.commit()
        r2 = await repo.aggregate_wallet_metrics()
        assert len(r2) == 1
        assert r2[0]["trades_24h"] == r1[0]["trades_24h"] + 1
