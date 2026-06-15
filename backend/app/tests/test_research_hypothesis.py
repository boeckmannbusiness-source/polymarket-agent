from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_hypothesis import ResearchHypothesis
from app.repositories.research_hypothesis_repository import ResearchHypothesisRepository
from app.services.research_hypothesis_service import ResearchHypothesisService


@pytest.mark.asyncio
class TestResearchHypothesisModel:
    async def test_create_hypothesis(self, db_session: AsyncSession):
        h = ResearchHypothesis(
            wallet_address="wallet_a",
            hypothesis_text="Test hypothesis",
            confidence=0.85,
            classification="whale",
            supporting_signals={"signal_ids": ["sig1", "sig2"]},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(h)
        await db_session.commit()

        assert h.id is not None
        assert h.wallet_address == "wallet_a"
        assert h.hypothesis_text == "Test hypothesis"
        assert h.confidence == 0.85
        assert h.classification == "whale"

    async def test_hypothesis_defaults(self, db_session: AsyncSession):
        h = ResearchHypothesis(
            wallet_address="wallet_b",
            hypothesis_text="Default test",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(h)
        await db_session.commit()

        assert h.confidence == 0.0
        assert h.classification == "unknown"
        assert h.supporting_signals == {}
        assert h.score_1h is None
        assert h.score_24h is None


@pytest.mark.asyncio
class TestResearchHypothesisRepository:
    async def test_create_and_list_active(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        h1 = ResearchHypothesis(
            wallet_address="wallet_c",
            hypothesis_text="Active hypothesis",
            confidence=0.9,
            classification="momentum",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        h2 = ResearchHypothesis(
            wallet_address="wallet_d",
            hypothesis_text="Expired hypothesis",
            confidence=0.5,
            classification="retail",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            expires_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        await repo.create(h1)
        await repo.create(h2)

        active = await repo.list_active()
        assert len(active) == 1
        assert active[0].wallet_address == "wallet_c"

    async def test_purge_expired(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        h = ResearchHypothesis(
            wallet_address="wallet_e",
            hypothesis_text="To be purged",
            confidence=0.3,
            classification="unknown",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            expires_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        await repo.create(h)

        count = await repo.purge_expired()
        assert count == 1

        remaining = await repo.list_active()
        assert len(remaining) == 0

    async def test_get_by_wallet_and_classification(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        h = ResearchHypothesis(
            wallet_address="wallet_f",
            hypothesis_text="Find me",
            confidence=0.75,
            classification="whale",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await repo.create(h)

        found = await repo.get_active_by_wallet_and_classification("wallet_f", "whale")
        assert found is not None
        assert found.hypothesis_text == "Find me"

        not_found = await repo.get_active_by_wallet_and_classification("wallet_f", "momentum")
        assert not_found is None

        no_match = await repo.get_active_by_wallet_and_classification("nonexistent", "whale")
        assert no_match is None

    async def test_get_by_wallet_and_classification_expired(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        h = ResearchHypothesis(
            wallet_address="wallet_g",
            hypothesis_text="Expired",
            confidence=0.4,
            classification="retail",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            expires_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        await repo.create(h)

        found = await repo.get_active_by_wallet_and_classification("wallet_g", "retail")
        assert found is None

    async def test_list_active_orders_by_confidence(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        now = datetime.now(timezone.utc)
        low = ResearchHypothesis(
            wallet_address="wallet_low", hypothesis_text="Low confidence",
            confidence=0.3, classification="unknown",
            created_at=now, expires_at=now + timedelta(days=7),
        )
        high = ResearchHypothesis(
            wallet_address="wallet_high", hypothesis_text="High confidence",
            confidence=0.9, classification="momentum",
            created_at=now, expires_at=now + timedelta(days=7),
        )
        await repo.create(high)
        await repo.create(low)

        active = await repo.list_active()
        assert active[0].wallet_address == "wallet_high"
        assert active[1].wallet_address == "wallet_low"

    async def test_purge_no_expired(self, db_session: AsyncSession):
        repo = ResearchHypothesisRepository(db_session)
        h = ResearchHypothesis(
            wallet_address="wallet_h",
            hypothesis_text="Not expired",
            confidence=0.6,
            classification="retail",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        await repo.create(h)

        count = await repo.purge_expired()
        assert count == 0


@pytest.mark.asyncio
class TestResearchHypothesisService:
    async def test_generate_from_score(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        h = await svc.generate_from_score(
            wallet_address="wallet_score",
            score=0.85, score_1h=0.8, score_24h=0.85,
            confidence=0.9, classification="whale",
            supporting_signals={"signal_ids": ["sig1"]},
        )
        assert h.wallet_address == "wallet_score"
        assert h.confidence == 0.9
        assert h.classification == "whale"
        assert "whale-like" in h.hypothesis_text
        assert h.expires_at is not None
        assert h.created_at is not None

    async def test_generate_from_score_unknown(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        h = await svc.generate_from_score(
            wallet_address="wallet_unknown",
            score=0.2, score_1h=0.1, score_24h=0.2,
            confidence=0.1, classification="unknown",
        )
        assert h.classification == "unknown"
        assert "insufficient data" in h.hypothesis_text

    async def test_generate_batch_creates_new(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        scored_wallets = [
            {"wallet_address": "w1", "score": 0.8, "score_1h": 0.7, "score_24h": 0.8,
             "confidence": 0.9, "classification": "whale"},
            {"wallet_address": "w2", "score": 0.5, "score_1h": 0.4, "score_24h": 0.5,
             "confidence": 0.6, "classification": "momentum"},
        ]
        results = await svc.generate_batch(scored_wallets)
        assert len(results) == 2

    async def test_generate_batch_updates_existing_classification(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        h1 = await svc.generate_from_score(
            wallet_address="w_dup", score=0.8, score_1h=0.7, score_24h=0.8,
            confidence=0.9, classification="whale",
        )
        scored = [
            {"wallet_address": "w_dup", "score": 0.85, "score_1h": 0.75, "score_24h": 0.85,
             "confidence": 0.95, "classification": "whale"},
        ]
        results = await svc.generate_batch(scored)
        assert len(results) == 1
        assert results[0].wallet_address == "w_dup"
        assert results[0].classification == "whale"
        assert results[0].confidence == 0.95

    async def test_generate_batch_allows_new_classification(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        await svc.generate_from_score(
            wallet_address="w_change", score=0.8, score_1h=0.7, score_24h=0.8,
            confidence=0.9, classification="whale",
        )
        scored = [
            {"wallet_address": "w_change", "score": 0.5, "score_1h": 0.4, "score_24h": 0.5,
             "confidence": 0.6, "classification": "momentum"},
        ]
        results = await svc.generate_batch(scored)
        assert len(results) == 1
        assert results[0].classification == "momentum"

    async def test_purge_expired(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        await svc.generate_from_score(
            wallet_address="w_purge", score=0.5, score_1h=0.4, score_24h=0.5,
            confidence=0.6, classification="retail",
        )
        # No expired hypotheses should exist
        count = await svc.purge_expired()
        assert count == 0

    async def test_hypothesis_text_deterministic(self, db_session: AsyncSession):
        svc = ResearchHypothesisService(db_session)
        h1 = await svc.generate_from_score(
            wallet_address="wallet_det", score=0.9, score_1h=0.8, score_24h=0.9,
            confidence=0.95, classification="whale",
        )
        h2 = await svc.generate_from_score(
            wallet_address="wallet_det2", score=0.9, score_1h=0.8, score_24h=0.9,
            confidence=0.95, classification="whale",
        )
        assert h1.hypothesis_text != h2.hypothesis_text
        assert "wallet_det" in h1.hypothesis_text
        assert "wallet_det2" in h2.hypothesis_text
