from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.research_hypothesis import ResearchHypothesis


class ResearchHypothesisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, hypothesis: ResearchHypothesis) -> ResearchHypothesis:
        self.db.add(hypothesis)
        await self.db.commit()
        await self.db.refresh(hypothesis)
        return hypothesis

    async def list_active(self, skip: int = 0, limit: int = 50) -> Sequence[ResearchHypothesis]:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ResearchHypothesis)
            .where(ResearchHypothesis.expires_at > now)
            .order_by(ResearchHypothesis.confidence.desc())
            .offset(skip)
            .limit(limit),
        )
        return result.scalars().all()

    async def purge_expired(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            text("DELETE FROM research_hypotheses WHERE expires_at <= :now"),
            {"now": now},
        )
        await self.db.commit()
        return result.rowcount or 0

    async def get_active_by_wallet_and_classification(
        self, wallet_address: str, classification: str,
    ) -> ResearchHypothesis | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(ResearchHypothesis)
            .where(ResearchHypothesis.wallet_address == wallet_address)
            .where(ResearchHypothesis.classification == classification)
            .where(ResearchHypothesis.expires_at > now)
            .order_by(ResearchHypothesis.confidence.desc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def update_hypothesis(
        self, hypothesis: ResearchHypothesis, **kwargs,
    ) -> ResearchHypothesis:
        for key, value in kwargs.items():
            setattr(hypothesis, key, value)
        await self.db.commit()
        await self.db.refresh(hypothesis)
        return hypothesis
