from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient

from app.models.smart_wallet import SmartWallet
from app.models.wallet_trade import SolanaWalletTrade
from app.models.research_trade import ResearchTrade


SIGNALS_URL = "/api/v1/signals/solana"


@pytest.mark.asyncio
class TestSolanaSignalsAPI:
    async def _seed_signal(
        self, db_session, wallet_address="wallet_a", strategy="high_score_entry",
        status="open",
    ) -> ResearchTrade:
        wallet = SmartWallet(
            wallet_address=wallet_address, source="test",
            first_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(wallet)
        await db_session.flush()

        trade = SolanaWalletTrade(
            wallet_id=wallet.id,
            tx_signature=f"tx_{wallet_address}",
            mint_address="mint1",
            side="buy", size_usd=1000.0, price_usd=2.0,
            block_time=datetime.now(timezone.utc),
        )
        db_session.add(trade)
        await db_session.flush()

        signal = ResearchTrade(
            signal_id=f"sig_{wallet_address}",
            strategy=strategy,
            wallet_trade_id=trade.id,
            entry_price=100.0,
            confidence=0.8,
            status=status,
            opened_at=datetime.now(timezone.utc),
        )
        db_session.add(signal)
        await db_session.commit()
        return signal

    async def test_list_signals_returns_data(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session)
        resp = await client.get(SIGNALS_URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_list_signals_includes_wallet_fields(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session, wallet_address="wallet_score_test")
        with patch(
            "app.api.solana_signals.WalletScoringService.compute_score",
            return_value={
                "wallet_address": "wallet_score_test",
                "score": 0.85, "score_1h": 0.8, "score_24h": 0.85,
                "confidence": 0.9, "classification": "whale",
            },
        ):
            resp = await client.get(SIGNALS_URL, headers={"x-admin-key": "test"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) >= 1
            item = next(s for s in data if s.get("wallet_address") == "wallet_score_test")
            assert item["wallet_score"] == 0.85
            assert item["wallet_score_1h"] == 0.8
            assert item["wallet_score_24h"] == 0.85
            assert item["wallet_confidence"] == 0.9
            assert item["wallet_classification"] == "whale"

    async def test_list_signals_sort_by_score_desc(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session, wallet_address="w_low")
        await self._seed_signal(db_session, wallet_address="w_high")

        fake_scores = {
            "w_low": {
                "wallet_address": "w_low", "score": 0.3, "score_1h": 0.2,
                "score_24h": 0.3, "confidence": 0.4, "classification": "retail",
            },
            "w_high": {
                "wallet_address": "w_high", "score": 0.9, "score_1h": 0.85,
                "score_24h": 0.9, "confidence": 0.95, "classification": "whale",
            },
        }

        def fake_batch(metrics_list):
            return [fake_scores.get(m.get("wallet_address", ""), fake_scores["w_high"]) for m in metrics_list]

        with patch(
            "app.api.solana_signals.WalletScoringService.compute_scores_batch",
            side_effect=fake_batch,
        ):
            resp = await client.get(SIGNALS_URL, headers={"x-admin-key": "test"})
            data = resp.json()
            assert data[0]["wallet_address"] == "w_high"
            assert data[1]["wallet_address"] == "w_low"

    async def test_min_confidence_filter(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session, wallet_address="w_conf_low")
        await self._seed_signal(db_session, wallet_address="w_conf_high")

        fake_scores = {
            "w_conf_low": {
                "wallet_address": "w_conf_low", "score": 0.3, "score_1h": 0.2,
                "score_24h": 0.3, "confidence": 0.2, "classification": "unknown",
            },
            "w_conf_high": {
                "wallet_address": "w_conf_high", "score": 0.8, "score_1h": 0.7,
                "score_24h": 0.8, "confidence": 0.9, "classification": "whale",
            },
        }

        def fake_batch(metrics_list):
            return [fake_scores.get(m.get("wallet_address", ""), fake_scores["w_conf_high"]) for m in metrics_list]

        with patch(
            "app.api.solana_signals.WalletScoringService.compute_scores_batch",
            side_effect=fake_batch,
        ):
            resp = await client.get(
                SIGNALS_URL + "?min_confidence=0.5",
                headers={"x-admin-key": "test"},
            )
            data = resp.json()
            assert len(data) == 1
            assert data[0]["wallet_address"] == "w_conf_high"

    async def test_strategy_filter(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session, wallet_address="w_strat_a", strategy="momentum")
        await self._seed_signal(db_session, wallet_address="w_strat_b", strategy="high_score_entry")
        resp = await client.get(
            SIGNALS_URL + "?strategy=momentum",
            headers={"x-admin-key": "test"},
        )
        data = resp.json()
        for s in data:
            assert s["strategy"] == "momentum"

    async def test_status_filter_open(self, client: AsyncClient, db_session):
        await self._seed_signal(db_session, wallet_address="w_open", status="open")
        await self._seed_signal(db_session, wallet_address="w_closed", status="closed")
        resp = await client.get(
            SIGNALS_URL + "?status=open",
            headers={"x-admin-key": "test"},
        )
        data = resp.json()
        for s in data:
            assert s["status"] == "open"

    async def test_pagination(self, client: AsyncClient, db_session):
        for i in range(5):
            await self._seed_signal(db_session, wallet_address=f"w_page_{i}")
        resp = await client.get(
            SIGNALS_URL + "?skip=0&limit=2",
            headers={"x-admin-key": "test"},
        )
        data = resp.json()
        assert len(data) <= 2

    async def test_get_single_signal(self, client: AsyncClient, db_session):
        signal = await self._seed_signal(db_session, wallet_address="w_single")
        resp = await client.get(
            f"{SIGNALS_URL}/{signal.id}",
            headers={"x-admin-key": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(signal.id)
        assert data["wallet_address"] == "w_single"
