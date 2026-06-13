import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import settings
from app.core.events import EventBus
from app.models.wallet_trade import SolanaWalletTrade
from app.repositories.smart_wallet_repository import SmartWalletRepository
from app.repositories.wallet_trade_repository import WalletTradeRepository
from app.schemas.helius import HeliusTransaction
from app.services.birdeye_service import BirdeyeClient, BirdeyeEnrichmentService, MemoryCache
from app.services.helius_service import HeliusService


def _make_mint() -> str:
    return "So11111111111111111111111111111111111111112"


def _make_tx_sig(counter: int = 1) -> str:
    return f"5KtNc4DgTpGqXQY7mJzR8vL2Wf9h1A3s6d0F4gHj{counter:0>28}"


def _make_wallet_address() -> str:
    return "GwzBgrXx4JmZ6YqTnR9vL2Wf7Hk1Np3s5d0F8cBa"


def _build_swap_tx(
    mint: str = _make_mint(),
    sig: str = None,
    wallet: str = _make_wallet_address(),
    timestamp: int = 1750000000,
    slot: int = 284195632,
    token_amount: float = 0.5,
) -> dict:
    if sig is None:
        sig = _make_tx_sig()
    return {
        "type": "SWAP",
        "signature": sig,
        "timestamp": timestamp,
        "slot": slot,
        "fee": 5000,
        "description": "Swapped 100 USDC for 0.5 SOL on Jupiter",
        "accounts": [wallet],
        "tokenTransfers": [
            {
                "mint": mint,
                "token_amount": token_amount,
                "from_user_account": wallet,
                "to_user_account": "vault_account",
            },
        ],
        "nativeTransfers": [],
        "accountData": [],
        "source": "JUPITER",
    }


class TestMemoryCache:
    def test_get_returns_none_for_missing_key(self):
        cache = MemoryCache(ttl_seconds=60, maxsize=100)
        assert cache.get("missing") is None

    def test_get_returns_cached_value_within_ttl(self):
        cache = MemoryCache(ttl_seconds=60, maxsize=100)
        cache.set("test_mint", 123.45)
        assert cache.get("test_mint") == 123.45

    def test_get_returns_none_after_ttl_expires(self):
        cache = MemoryCache(ttl_seconds=0, maxsize=100)
        cache.set("test_mint", 123.45)
        import time
        time.sleep(0.001)
        assert cache.get("test_mint") is None

    def test_set_evicts_oldest_when_full(self):
        cache = MemoryCache(ttl_seconds=60, maxsize=2)
        cache.set("a", 1.0)
        cache.set("b", 2.0)
        cache.set("c", 3.0)
        assert cache.get("a") is None
        assert cache.get("b") == 2.0
        assert cache.get("c") == 3.0


@pytest.mark.asyncio
class TestBirdeyeClient:
    async def test_get_token_price_returns_value(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": True, "data": {"value": 123.45}}

        client = BirdeyeClient(api_key="test_key")
        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_resp)):
            price = await client.get_token_price(_make_mint())

        assert price == 123.45

    async def test_get_token_price_returns_none_when_no_api_key(self):
        client = BirdeyeClient(api_key="")
        price = await client.get_token_price(_make_mint())
        assert price is None

    async def test_get_token_price_returns_none_on_http_error(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp,
        )

        client = BirdeyeClient(api_key="test_key")
        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_resp)):
            price = await client.get_token_price(_make_mint())

        assert price is None

    async def test_get_token_price_returns_none_on_rate_limit(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 429

        client = BirdeyeClient(api_key="test_key")
        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_resp)):
            price = await client.get_token_price(_make_mint())

        assert price is None

    async def test_get_token_price_returns_none_on_success_false(self):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"success": False, "message": "rate limit"}

        client = BirdeyeClient(api_key="test_key")
        with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_resp)):
            price = await client.get_token_price(_make_mint())

        assert price is None


@pytest.mark.asyncio
class TestBirdeyeEnrichmentService:
    async def test_enrich_trade_updates_price_usd(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(1),
            mint_address=_make_mint(),
            side="buy",
            size_usd=0.5,
            price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )
        assert trade.price_usd == Decimal("0.0")

        service = BirdeyeEnrichmentService(db_session)
        with patch.object(service.client, "get_token_price", new=AsyncMock(return_value=123.45)):
            result = await service.enrich_trade(trade.id)
        assert result is True

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("123.45")

    async def test_enrich_trade_recalculates_size_usd(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(2),
            mint_address=_make_mint(),
            side="sell",
            size_usd=10.0,
            price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        with patch.object(service.client, "get_token_price", new=AsyncMock(return_value=50.0)):
            result = await service.enrich_trade(trade.id, token_amount=10.0)
        assert result is True

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("50.0")
        assert updated.size_usd == Decimal("500.0")

    async def test_enrich_trade_skips_when_price_already_set(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(3),
            mint_address=_make_mint(),
            side="buy",
            size_usd=0.5,
            price_usd=100.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        with patch.object(service.client, "get_token_price", new=AsyncMock(return_value=200.0)):
            result = await service.enrich_trade(trade.id)
        assert result is True

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("100.0")

    async def test_enrich_trade_returns_false_for_missing_trade(self, db_session):
        service = BirdeyeEnrichmentService(db_session)
        result = await service.enrich_trade(uuid.uuid4())
        assert result is False

    async def test_enrich_trade_returns_false_when_price_unavailable(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(4),
            mint_address=_make_mint(),
            side="buy",
            size_usd=0.5,
            price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        with patch.object(service.client, "get_token_price", new=AsyncMock(return_value=None)):
            result = await service.enrich_trade(trade.id)
        assert result is False

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("0.0")

    async def test_enrich_batch_counts_successes(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        mints = ["mint_a_111111111111111111111111111111",
                 "mint_b_222222222222222222222222222222",
                 "mint_c_333333333333333333333333333333"]
        t1 = await repo.create_trade(
            wallet_id=wallet.id, tx_signature=_make_tx_sig(5),
            mint_address=mints[0], side="buy",
            size_usd=0.5, price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )
        t2 = await repo.create_trade(
            wallet_id=wallet.id, tx_signature=_make_tx_sig(6),
            mint_address=mints[1], side="sell",
            size_usd=1.0, price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )
        t3 = await repo.create_trade(
            wallet_id=wallet.id, tx_signature=_make_tx_sig(7),
            mint_address=mints[2], side="buy",
            size_usd=2.0, price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        price_map = {mints[0]: 10.0, mints[1]: None, mints[2]: 30.0}

        with patch.object(service.client, "get_token_price", new=AsyncMock(side_effect=lambda m: price_map.get(m))):
            count = await service.enrich_batch([t1.id, t2.id, t3.id])

        assert count == 2

    async def test_enrichment_cache_hit_avoids_api_call(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(8),
            mint_address=_make_mint(),
            side="buy",
            size_usd=0.5,
            price_usd=0.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        service.cache.set(_make_mint(), 99.99)

        with patch.object(service.client, "get_token_price", new=AsyncMock()) as mock_get:
            result = await service.enrich_trade(trade.id)

        assert result is True
        mock_get.assert_not_called()

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("99.99")


@pytest.mark.asyncio
class TestHeliusServiceIntegration:
    @pytest.fixture(autouse=True)
    def _mock_eventbus(self):
        with patch.object(EventBus, "publish", new=AsyncMock()):
            yield

    async def test_trade_enriched_after_webhook(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx(token_amount=0.5)
        tx = HeliusTransaction(**tx_raw)

        with patch.object(service.birdeye.client, "get_token_price", new=AsyncMock(return_value=200.0)):
            count = await service.process_transaction(tx)
        assert count == 1

        trade = await service.trade_repo.get_by_signature(tx.signature)
        assert trade is not None
        assert trade.price_usd == Decimal("200.0")
        assert trade.size_usd == Decimal("100.0")

    async def test_event_payload_contains_enriched_price(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx(token_amount=2.0)
        tx = HeliusTransaction(**tx_raw)

        with patch.object(service.birdeye.client, "get_token_price", new=AsyncMock(return_value=50.0)):
            count = await service.process_transaction(tx)
        assert count == 1

        trade = await service.trade_repo.get_by_signature(tx.signature)
        assert trade.price_usd == Decimal("50.0")
        assert trade.size_usd == Decimal("100.0")

        EventBus.publish.assert_awaited_once()
        call_args = EventBus.publish.await_args
        payload = call_args.args[3]
        assert payload["price_usd"] == 50.0
        assert payload["size_usd"] == 100.0

    async def test_trade_created_even_when_enrichment_fails(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx(token_amount=1.0)
        tx = HeliusTransaction(**tx_raw)

        with patch.object(service.birdeye.client, "get_token_price", new=AsyncMock(side_effect=ConnectionError("API down"))):
            count = await service.process_transaction(tx)
        assert count == 1

        trade = await service.trade_repo.get_by_signature(tx.signature)
        assert trade is not None
        assert trade.price_usd == Decimal("0.0")

    async def test_already_enriched_trade_not_overwritten(self, db_session):
        repo = WalletTradeRepository(db_session)
        wallet_repo = SmartWalletRepository(db_session)
        wallet = await wallet_repo.create_wallet(
            wallet_address=_make_wallet_address(),
            source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        trade = await repo.create_trade(
            wallet_id=wallet.id,
            tx_signature=_make_tx_sig(99),
            mint_address=_make_mint(),
            side="buy",
            size_usd=0.5,
            price_usd=100.0,
            block_time=datetime.now(timezone.utc),
        )

        service = BirdeyeEnrichmentService(db_session)
        with patch.object(service.client, "get_token_price", new=AsyncMock(return_value=999.0)):
            result = await service.enrich_trade(trade.id)
        assert result is True

        updated = await repo.get_by_id(trade.id)
        assert updated.price_usd == Decimal("100.0")
