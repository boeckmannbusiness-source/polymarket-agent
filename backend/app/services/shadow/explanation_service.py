import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.decision_explanation import DecisionExplanation
from app.core.logging import logger

class ExplanationService:
    """
    Service for storing and retrieving decision explanations.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def store_explanation(
        self,
        decision_id: uuid.UUID,
        strategy_inputs: Dict[str, Any],
        expected_outcome: Optional[str] = None,
        confidence_reasoning: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        replay_reference: Optional[str] = None
    ) -> DecisionExplanation:
        """
        Stores an explanation for a decision.
        """
        explanation = DecisionExplanation(
            decision_id=decision_id,
            strategy_inputs=strategy_inputs,
            expected_outcome=expected_outcome,
            confidence_reasoning=confidence_reasoning,
            rejection_reason=rejection_reason,
            replay_reference=replay_reference
        )
        self.db.add(explanation)
        await self.db.flush() # Ensure it's sent to DB but let caller commit
        return explanation

    async def get_explanation(self, decision_id: uuid.UUID) -> Optional[DecisionExplanation]:
        """
        Retrieves an explanation for a decision.
        """
        result = await self.db.execute(
            select(DecisionExplanation).where(DecisionExplanation.decision_id == decision_id)
        )
        return result.scalars().first()
