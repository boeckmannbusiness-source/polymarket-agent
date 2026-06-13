import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.research_trade_repository import ResearchTradeRepository
from app.repositories.smart_wallet_repository import SmartWalletRepository
from app.repositories.wallet_trade_repository import WalletTradeRepository
from app.services.signal_seed_service import SignalSeedService


def _make_mint() -> str:
    return "So11111111111111111111111111111111111111112"


def _make_wallet() -> str:
    return "GwzBgrXx4JmZ6YqTnR9vL2Wf7Hk1Np3s5d0F8cBa"


def _event_data(
    wallet: str = _make_wallet(),
    mint: str = _make_mint(),
    price: float = 150.0,
    trade_id: str | None = None,
) -> dict:
    return {
        "wallet_address": wallet,
        "mint_address": mint,
        "side": "buy",
        "size_usd": 100.0,
        "price_usd": price,
        "tx_signature": "x" * 88,
        "slot": 284195632,
        "block_time": "2026-06-13T07:00:00+00:00",
        "trade_id": trade_id or str(uuid.uuid4()),
    }


@pytest.mark.asyncio
class TestSignalSeedService:
    async def test_high_score_wallet_generates_signal(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(wallet.id, score=0.85)

        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data())
        assert count == 1

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 1
        assert research[0].strategy == "high_score_entry"
        assert research[0].confidence == Decimal("0.85")

    async def test_low_score_wallet_no_signal(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(wallet.id, score=0.3)

        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data())
        assert count == 0

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 0

    async def test_price_usd_zero_no_signal(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(wallet.id, score=0.85)

        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data(price=0.0))
        assert count == 0

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 0

    async def test_null_price_usd_no_signal(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(wallet.id, score=0.85)

        data = _event_data()
        data["price_usd"] = None
        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(data)
        assert count == 0

    async def test_unknown_wallet_no_signal(self, db_session):
        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data())
        assert count == 0

    async def test_missing_wallet_address_no_signal(self, db_session):
        data = _event_data()
        data["wallet_address"] = None
        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(data)
        assert count == 0

    async def test_token_velocity_spike_generates_signal(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        trade_repo = WalletTradeRepository(db_session)

        wallets = []
        for i in range(3):
            addr = f"wallet_{i}_111111111111111111111111111111"
            w = await wallet_repo.create_wallet(
                wallet_address=addr,
                source="test",
                first_seen_at=datetime.now(timezone.utc),
            )
            wallets.append(w)

        mint = _make_mint()
        for w in wallets:
            await trade_repo.create_trade(
                wallet_id=w.id,
                tx_signature=f"sig_velocity_{w.id}_{i}",
                mint_address=mint,
                side="buy",
                size_usd=100.0,
                price_usd=150.0,
                block_time=datetime.now(timezone.utc),
            )

        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )

        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data(wallet=_make_wallet()))
        assert count == 1

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 1
        assert research[0].strategy == "token_velocity_spike"

    async def test_both_high_score_and_velocity(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        trade_repo = WalletTradeRepository(db_session)

        wallets = []
        for i in range(3):
            addr = f"dual_{i}_11111111111111111111111111111111"
            w = await wallet_repo.create_wallet(
                wallet_address=addr,
                source="test",
                first_seen_at=datetime.now(timezone.utc),
            )
            wallets.append(w)

        mint = _make_mint()
        for w in wallets:
            await trade_repo.create_trade(
                wallet_id=w.id,
                tx_signature=f"sig_dual_{w.id}",
                mint_address=mint,
                side="buy",
                size_usd=100.0,
                price_usd=150.0,
                block_time=datetime.now(timezone.utc),
            )

        high_score_wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(high_score_wallet.id, score=0.85)

        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data(wallet=_make_wallet()))
        assert count == 2

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 2
        strategies = {r.strategy for r in research}
        assert "high_score_entry" in strategies
        assert "token_velocity_spike" in strategies

    async def test_event_data_with_trade_id(self, db_session):
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        await wallet_repo.update_metrics(wallet.id, score=0.85)

        trade_id = uuid.uuid4()
        service = SignalSeedService(db_session)
        count = await service.evaluate_trade_event(_event_data(trade_id=str(trade_id)))
        assert count == 1

        research = await ResearchTradeRepository(db_session).list_open_positions()
        assert len(research) == 1
        assert research[0].wallet_trade_id == trade_id
