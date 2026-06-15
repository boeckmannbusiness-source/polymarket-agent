import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.events import EventBus
from app.repositories.smart_wallet_repository import SmartWalletRepository
from app.schemas.helius import HeliusTransaction, HeliusTokenTransfer
from app.services.helius_service import HeliusService


_sig_counter: int = 0


def _make_tx_sig() -> str:
    global _sig_counter
    _sig_counter += 1
    return f"5KtNc4DgTpGqXQY7mJzR8vL2Wf9h1A3s6d0F4gHj{_sig_counter:0>28}"


def _make_mint() -> str:
    return "So11111111111111111111111111111111111111112"


def _make_wallet_address() -> str:
    return "GwzBgrXx4JmZ6YqTnR9vL2Wf7Hk1Np3s5d0F8cBa"


def _build_swap_tx(
    mint: str = _make_mint(),
    sig: str = _make_tx_sig(),
    wallet: str = _make_wallet_address(),
    side: str = "buy",
    timestamp: int = 1750000000,
    slot: int = 284195632,
) -> dict:
    return {
        "type": "SWAP",
        "signature": sig,
        "timestamp": timestamp,
        "slot": slot,
        "fee": 5000,
        "description": f"Swapped 100 USDC for 0.5 SOL on Jupiter" if side == "buy" else f"Sold 0.5 SOL for 100 USDC",
        "accounts": [wallet],
        "tokenTransfers": [
            {
                "mint": mint,
                "token_amount": 0.5,
                "from_user_account": wallet,
                "to_user_account": "vault_account",
            },
        ],
        "nativeTransfers": [],
        "accountData": [],
        "source": "JUPITER",
    }


class TestHeliusSchemas:
    def test_valid_swap_transaction(self):
        raw = _build_swap_tx()
        tx = HeliusTransaction(**raw)
        assert tx.type == "SWAP"
        assert tx.signature == raw["signature"]
        assert tx.slot == 284195632

    def test_valid_token_transfer(self):
        tt = HeliusTokenTransfer(mint=_make_mint(), token_amount=0.5)
        assert tt.mint == _make_mint()
        assert tt.token_amount == 0.5

    def test_invalid_transaction_type_rejected(self):
        raw = _build_swap_tx()
        raw["type"] = "INVALID"
        with pytest.raises(Exception):
            HeliusTransaction(**raw)

    def test_short_signature_rejected(self):
        raw = _build_swap_tx()
        raw["signature"] = "tooshort"
        with pytest.raises(Exception):
            HeliusTransaction(**raw)


@pytest.mark.asyncio
class TestHeliusService:
    @pytest.fixture(autouse=True)
    def _mock_eventbus(self):
        with patch.object(EventBus, "publish", new=AsyncMock()):
            yield

    async def test_process_swap_trade(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx()
        tx = HeliusTransaction(**tx_raw)
        count = await service.process_transaction(tx)
        assert count == 1

        trade = await service.trade_repo.get_by_signature(tx.signature)
        assert trade is not None
        assert trade.tx_signature == tx.signature

    async def test_skip_non_swap(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx()
        tx_raw["type"] = "TRANSFER"
        count = await service.process_transaction(HeliusTransaction(**tx_raw))
        assert count == 0

    async def test_skip_duplicate_signature(self, db_session):
        service = HeliusService(db_session)
        tx = HeliusTransaction(**(_build_swap_tx()))
        count1 = await service.process_transaction(tx)
        count2 = await service.process_transaction(tx)
        assert count1 == 1
        assert count2 == 0

    async def test_skip_no_wallet(self, db_session):
        service = HeliusService(db_session)
        tx_raw = _build_swap_tx()
        tx_raw["accounts"] = []
        count = await service.process_transaction(HeliusTransaction(**tx_raw))
        assert count == 0

    async def test_process_batch(self, db_session):
        service = HeliusService(db_session)
        txs = [
            HeliusTransaction(**(_build_swap_tx(sig=_make_tx_sig(), mint=_make_mint()))),
            HeliusTransaction(**(_build_swap_tx(sig=_make_tx_sig(), mint=_make_mint()))),
        ]
        count = await service.process_batch(txs)
        assert count == 2

    async def test_ensure_wallet_creates_new(self, db_session):
        service = HeliusService(db_session)
        addr = _make_wallet_address()
        wallet = await service._ensure_wallet(addr)
        assert wallet is not None
        assert wallet.wallet_address == addr
        assert wallet.source == "helius_webhook"

    async def test_ensure_wallet_reuses_existing(self, db_session):
        service = HeliusService(db_session)
        addr = _make_wallet_address()
        w1 = await service._ensure_wallet(addr)
        w2 = await service._ensure_wallet(addr)
        assert w1.id == w2.id

    async def test_ensure_wallet_handles_integrityerror_race(self, db_session):
        service = HeliusService(db_session)
        addr = _make_wallet_address()

        real_create = service.wallet_repo.create_wallet

        async def race_create(*args, **kwargs):
            await real_create(*args, **kwargs)
            raise IntegrityError("test", "test", "test")

        with patch.object(service.wallet_repo, "create_wallet", side_effect=race_create):
            wallet = await service._ensure_wallet(addr)

        assert wallet is not None
        assert wallet.wallet_address == addr

    async def test_process_swap_trade_eventbus_failure(self, db_session):
        service = HeliusService(db_session)
        tx = HeliusTransaction(**(_build_swap_tx()))

        real_publish = EventBus.publish

        async def fail_publish(*args, **kwargs):
            raise ConnectionError("Redis unavailable")

        with patch.object(EventBus, "publish", new=fail_publish):
            count = await service.process_transaction(tx)

        assert count == 1

        trade = await service.trade_repo.get_by_signature(tx.signature)
        assert trade is not None


@pytest.mark.asyncio
class TestHeliusWebhookEndpoint:
    @pytest.fixture(autouse=True)
    def _mock_eventbus(self):
        with patch.object(EventBus, "publish", new=AsyncMock()):
            yield

    async def test_webhook_returns_ok(self, client: AsyncClient, db_session):
        tx_raw = _build_swap_tx()
        payload = [tx_raw]
        with patch.object(settings, "HELIUS_WEBHOOK_SECRET", ""):
            response = await client.post("/api/v1/webhooks/helius", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["processed"] == 1

    async def test_webhook_unauthenticated(self, client: AsyncClient):
        payload = [{"type": "SWAP", "signature": _make_tx_sig(), "tokenTransfers": []}]
        with patch.object(settings, "HELIUS_WEBHOOK_SECRET", "secret123"):
            response = await client.post(
                "/api/v1/webhooks/helius",
                json=payload,
                headers={"Authorization": "Bearer wrong_secret"},
            )
        assert response.status_code == 401

    async def test_webhook_authenticated(self, client: AsyncClient, db_session):
        tx_raw = _build_swap_tx()
        payload = [tx_raw]
        with patch.object(settings, "HELIUS_WEBHOOK_SECRET", "secret123"):
            response = await client.post(
                "/api/v1/webhooks/helius",
                json=payload,
                headers={"Authorization": "Bearer secret123"},
            )
        assert response.status_code == 200

    async def test_empty_payload(self, client: AsyncClient):
        with patch.object(settings, "HELIUS_WEBHOOK_SECRET", ""):
            response = await client.post("/api/v1/webhooks/helius", json=[])
        assert response.status_code == 200
        assert response.json()["processed"] == 0

    async def test_object_payload_with_transactions_key(self, client: AsyncClient, db_session):
        tx_raw = _build_swap_tx()
        payload = {"transactions": [tx_raw]}
        with patch.object(settings, "HELIUS_WEBHOOK_SECRET", ""):
            response = await client.post("/api/v1/webhooks/helius", json=payload)
        assert response.status_code == 200
        assert response.json()["processed"] == 1
