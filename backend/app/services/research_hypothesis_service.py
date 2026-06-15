import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.research_hypothesis import ResearchHypothesis
from app.repositories.research_hypothesis_repository import ResearchHypothesisRepository
from sqlalchemy.ext.asyncio import AsyncSession


CLASSIFICATION_HYPOTHESES = {
    "whale": (
        "Wallet {wallet_address} demonstrates whale-like behavior with "
        "high trade volume and consistent scoring. Likely an institutional "
        "or high-net-worth trader executing large-scale strategies."
    ),
    "momentum": (
        "Wallet {wallet_address} exhibits momentum trading patterns with "
        "moderate-to-high scoring. May be a systematic or semi-systematic "
        "trader capitalizing on short-term price movements."
    ),
    "retail": (
        "Wallet {wallet_address} shows retail-level trading activity. "
        "Lower scores and volumes suggest individual trader behavior."
    ),
    "unknown": (
        "Wallet {wallet_address} has insufficient data to classify "
        "trading behavior confidently. Additional observation required."
    ),
}


class ResearchHypothesisService:
    def __init__(self, db: AsyncSession):
        self.repo = ResearchHypothesisRepository(db)

    async def generate_from_score(
        self,
        wallet_address: str,
        score: float,
        score_1h: float,
        score_24h: float,
        confidence: float,
        classification: str,
        supporting_signals: dict[str, Any] | None = None,
    ) -> ResearchHypothesis:
        hypothesis_text = CLASSIFICATION_HYPOTHESES.get(
            classification,
            CLASSIFICATION_HYPOTHESES["unknown"],
        ).format(wallet_address=wallet_address)

        hypothesis = ResearchHypothesis(
            id=uuid.uuid4(),
            wallet_address=wallet_address,
            hypothesis_text=hypothesis_text,
            confidence=confidence,
            score_1h=score_1h,
            score_24h=score_24h,
            classification=classification,
            supporting_signals=supporting_signals or {},
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        return await self.repo.create(hypothesis)

    async def generate_batch(
        self,
        scored_wallets: list[dict[str, Any]],
    ) -> list[ResearchHypothesis]:
        results = []
        for sw in scored_wallets:
            wallet_addr = sw["wallet_address"]
            classification = sw.get("classification", "unknown")
            existing = await self.repo.get_active_by_wallet_and_classification(
                wallet_addr, classification,
            )
            if existing:
                h = await self.repo.update_hypothesis(
                    existing,
                    confidence=sw.get("confidence", 0.0),
                    score_1h=sw.get("score_1h", 0.0),
                    score_24h=sw.get("score_24h", 0.0),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                    supporting_signals=sw.get("supporting_signals"),
                )
            else:
                h = await self.generate_from_score(
                    wallet_address=wallet_addr,
                    score=sw.get("score", 0.0),
                    score_1h=sw.get("score_1h", 0.0),
                    score_24h=sw.get("score_24h", 0.0),
                    confidence=sw.get("confidence", 0.0),
                    classification=classification,
                    supporting_signals=sw.get("supporting_signals"),
                )
            results.append(h)
        return results

    async def purge_expired(self) -> int:
        return await self.repo.purge_expired()
