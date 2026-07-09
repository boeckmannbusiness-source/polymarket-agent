import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shadow_decision_log import ShadowDecisionLog
from app.domain.shadow.models import OutcomeReceipt
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
        predicted_probability: Optional[float] = None,
        admission_receipt_hash: Optional[str] = None,
        governor_decision: Optional[str] = None,
        certification_snapshot_hash: Optional[str] = None,
        predicted_direction: Optional[str] = None,
        execution_hash: Optional[str] = None,
        snapshot_hash: Optional[str] = None,
    ) -> ShadowDecisionLog:
        """
        Records a shadow decision in the ledger.
        """
        decision_id = uuid.uuid4()

        # Task 2: Apply deterministic sampling
        from app.services.shadow.sampling_service import ShadowSamplingService
        sampling_svc = ShadowSamplingService(self.db)
        sample_reason, audit_candidate, sampling_bucket = sampling_svc.get_sampling_result(decision_id)

        log_entry = ShadowDecisionLog(
            id=decision_id,
            timestamp=datetime.now(timezone.utc),
            market_id=market_id,
            signal_id=signal_id,
            strategy_id=strategy_id,
            confidence=confidence,
            decision=decision,
            simulated_size=simulated_size,
            simulated_entry_price=simulated_entry_price,
            expected_ev=expected_ev,
            predicted_direction=predicted_direction,
            predicted_probability=predicted_probability,
            execution_hash=execution_hash,
            replay_hash=replay_hash,
            replay_match=replay_match,
            snapshot_hash=snapshot_hash,
            decision_status="OPEN",
            admission_receipt_hash=admission_receipt_hash,
            governor_decision=governor_decision,
            certification_version=certification_version,
            certification_snapshot_hash=certification_snapshot_hash,
            certification_violation=certification_violation,
            regime=regime,
            regime_confidence=regime_confidence,
            approval_reason=approval_reason,
            rejection_reason=rejection_reason,
            sample_reason=sample_reason,
            audit_candidate=audit_candidate,
            sampling_bucket=sampling_bucket,
        )

        self.db.add(log_entry)
        await self.db.flush()

        logger.info(
            "shadow_decision_recorded",
            decision_id=str(log_entry.id),
            market_id=market_id,
            strategy_id=strategy_id,
            decision=decision
        )
        return log_entry

    async def store_outcome_receipt(self, receipt: OutcomeReceipt) -> Optional[ShadowDecisionLog]:
        """
        Updates a shadow decision with its OutcomeReceipt.
        """
        result = await self.db.execute(
            select(ShadowDecisionLog).where(ShadowDecisionLog.id == receipt.decision_id)
        )
        log_entry = result.scalar_one_or_none()

        if not log_entry:
            logger.warning("shadow_decision_not_found", decision_id=str(receipt.decision_id))
            return None

        log_entry.simulated_exit_price = receipt.resolution_price
        log_entry.actual_ev = receipt.realized_ev
        log_entry.realized_ev = receipt.realized_ev
        log_entry.outcome_timestamp = receipt.timestamp
        log_entry.decision_status = "RESOLVED"
        # We could add more fields to model if needed, but these are core for now.

        await self.db.flush()

        logger.info(
            "shadow_outcome_stored",
            decision_id=str(log_entry.id),
            actual_ev=receipt.realized_ev
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
        log_entry.realized_ev = actual_ev
        log_entry.decision_status = "RESOLVED"

        await self.db.flush()

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
