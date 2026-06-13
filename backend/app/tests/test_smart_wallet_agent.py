import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.smart_wallet import SmartWallet
from app.services.smart_wallet_agent import SmartWalletAgent


def _make_address() -> str:
    return "GwzBgrXx4JmZ6YqTnR9vL2Wf7Hk1Np3s5d0F8cBa"


def _make_trade_event(wallet_address: str = _make_address()) -> dict:
    return {
        "wallet_address": wallet_address,
        "mint_address": "So11111111111111111111111111111111111111112",
        "side": "buy",
        "size_usd": 100.0,
        "price_usd": 150.0,
        "tx_signature": "5KtNc4DgTpGqXQY7mJzR8vL2Wf9h1A3s6d0F4gHj00000000000000000000001",
        "slot": 284195632,
        "block_time": "2026-06-15T15:06:40+00:00",
    }


@pytest.mark.asyncio
class TestSmartWalletAgent:
    async def _create_wallet(self, db_session, address: str | None = None) -> SmartWallet:
        from app.repositories.smart_wallet_repository import SmartWalletRepository

        repo = SmartWalletRepository(db_session)
        return await repo.create_wallet(
            wallet_address=address or _make_address(),
            source="helius_webhook",
            first_seen_at=datetime.now(timezone.utc),
        )

    async def test_handle_trade_event_updates_metrics(self, db_session):
        wallet = await self._create_wallet(db_session)
        assert wallet.total_trades == 0

        agent = SmartWalletAgent(db_session)
        event = _make_trade_event(wallet_address=wallet.wallet_address)
        await agent.handle_trade_event(event)

        updated = await agent.wallet_repo.get_by_id(wallet.id)
        assert updated is not None
        assert updated.total_trades == 1

    async def test_handle_trade_event_unknown_wallet(self, db_session):
        agent = SmartWalletAgent(db_session)
        event = _make_trade_event(wallet_address="11111111111111111111111111111111111111111111")
        await agent.handle_trade_event(event)

    async def test_handle_trade_event_missing_wallet_address(self, db_session):
        agent = SmartWalletAgent(db_session)
        await agent.handle_trade_event({"side": "buy"})

    async def test_handle_trade_event_increments_multiple(self, db_session):
        wallet = await self._create_wallet(db_session)
        agent = SmartWalletAgent(db_session)
        event = _make_trade_event(wallet_address=wallet.wallet_address)

        for _ in range(5):
            await agent.handle_trade_event(event)

        updated = await agent.wallet_repo.get_by_id(wallet.id)
        assert updated.total_trades == 5

    async def test_handle_trade_event_multiple_wallets(self, db_session):
        w1 = await self._create_wallet(db_session, _make_address())
        w2 = await self._create_wallet(db_session, "22222222222222222222222222222222222222222222")
        agent = SmartWalletAgent(db_session)

        await agent.handle_trade_event(_make_trade_event(wallet_address=w1.wallet_address))
        await agent.handle_trade_event(_make_trade_event(wallet_address=w2.wallet_address))

        assert (await agent.wallet_repo.get_by_id(w1.id)).total_trades == 1
        assert (await agent.wallet_repo.get_by_id(w2.id)).total_trades == 1

    async def test_loop_subscribes_with_correct_consumer_group(self):
        from app.core.stream_registry import StreamRegistry

        config = StreamRegistry.get("solana:trade:detected")
        assert config is not None
        assert "smart_wallet_agent" in config.consumer_groups
