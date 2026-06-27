import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shadow_decision_log import ShadowDecisionLog
from app.core.logging import logger

class ShadowLedger:
    """
    Shadow Decision Ledger
    Records every shadow decision for reproducibility and evaluation.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_decision(
        self,
        market_id: str,
        signal_id: str,
        strategy_id: str,
        confidence: float,
        decision: str,
        simulated_size: float,
        simulated_entry_price: float,
        expected_ev: float,
        replay_hash: str,
        replay_match: bool,
        certification_version: str,
        certification_violation: bool = False,
        regime: Optional[str] = None,
        regime_confidence: Optional[float] = None,
        approval_reason: Optional[str] = None,
        rejection_reason: Optional[str] = None,
    ) -> ShadowDecisionLog:
        """
        Records a shadow decision in the ledger.
        """
        log_entry = ShadowDecisionLog(
            id=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            market_id=market_id,
            signal_id=signal_id,
            strategy_id=strategy_id,
            confidence=confidence,
            decision=decision,
            simulated_size=simulated_size,
            simulated_entry_price=simulated_entry_price,
            expected_ev=expected_ev,
            replay_hash=replay_hash,
            replay_match=replay_match,
            certification_version=certification_version,
            certification_violation=certification_violation,
            regime=regime,
            regime_confidence=regime_confidence,
            approval_reason=approval_reason,
            rejection_reason=rejection_reason,
        )

        self.db.add(log_entry)
        await self.db.commit()
        await self.db.refresh(log_entry)

        logger.info(
            "shadow_decision_recorded",
            decision_id=str(log_entry.id),
            market_id=market_id,
            strategy_id=strategy_id,
            decision=decision
        )
        return log_entry

    async def update_outcome(
        self,
        decision_id: uuid.UUID,
        simulated_exit_price: float,
        actual_ev: float
    ) -> Optional[ShadowDecisionLog]:
        """
        Updates a shadow decision with its outcome (exit price and actual EV).
        """
        result = await self.db.execute(
            select(ShadowDecisionLog).where(ShadowDecisionLog.id == decision_id)
        )
        log_entry = result.scalar_one_or_none()

        if not log_entry:
            logger.warning("shadow_decision_not_found", decision_id=str(decision_id))
            return None

        log_entry.simulated_exit_price = simulated_exit_price
        log_entry.actual_ev = actual_ev

        await self.db.commit()
        await self.db.refresh(log_entry)

        logger.info(
            "shadow_outcome_updated",
            decision_id=str(log_entry.id),
            actual_ev=actual_ev
        )
        return log_entry

    async def get_decisions(
        self,
        strategy_id: Optional[str] = None,
        limit: int = 100
    ) -> list[ShadowDecisionLog]:
        """
        Retrieves shadow decisions from the ledger.
        """
        query = select(ShadowDecisionLog).order_by(ShadowDecisionLog.timestamp.desc())
        if strategy_id:
            query = query.where(ShadowDecisionLog.strategy_id == strategy_id)

        query = query.limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
