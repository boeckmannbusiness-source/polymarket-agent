import math
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.shadow_decision_log import ShadowDecisionLog
from app.domain.shadow.models import OutcomeReceipt
from app.core.logging import logger

class OutcomeClosureEngine:
    """
    Build outcome resolution for completed decisions.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_decision(
        self,
        decision_id: UUID,
        resolution_price: float,
        resolution_source: str = "manual"
    ) -> OutcomeReceipt:
        """
        When market outcome becomes available: resolve decision, compute metrics, and return receipt.
        """
        result = await self.db.execute(
            select(ShadowDecisionLog).where(ShadowDecisionLog.id == decision_id)
        )
        log_entry = result.scalar_one_or_none()

        if not log_entry:
            raise ValueError(f"ShadowDecisionLog not found: {decision_id}")

        # Compute realized_ev
        # Simple realized EV calculation: size * (resolution_price - entry_price)
        # Handle direction
        entry_price = log_entry.simulated_entry_price or 0.0
        size = log_entry.simulated_size or 0.0

        # PnL per unit
        pnl_per_unit = resolution_price - entry_price
        if log_entry.decision == "sell":
            pnl_per_unit = -pnl_per_unit

        realized_ev = size * pnl_per_unit
        win_loss = realized_ev > 0

        # Prediction error: (confidence - outcome)
        # Outcome is 1.0 if win, 0.0 if loss
        outcome_val = 1.0 if win_loss else 0.0
        prediction_error = abs((log_entry.confidence or 0.0) - outcome_val)

        # Calibration delta: (predicted_probability - actual_win_rate)
        # Since we are resolving one decision, actual_win_rate is outcome_val
        calibration_delta = (log_entry.predicted_probability or 0.0) - outcome_val

        now = datetime.now(timezone.utc)
        receipt = OutcomeReceipt(
            decision_id=decision_id,
            timestamp=now,
            realized_ev=realized_ev,
            win_loss=win_loss,
            calibration_delta=calibration_delta,
            prediction_error=prediction_error,
            resolution_price=resolution_price
        )

        # Update log entry
        log_entry.realized_ev = realized_ev
        log_entry.actual_ev = realized_ev
        log_entry.simulated_exit_price = resolution_price
        log_entry.outcome_timestamp = now
        log_entry.market_resolution_source = resolution_source
        # Transition OPEN -> CLOSED -> RESOLVED
        log_entry.decision_status = "CLOSED"
        await self.db.flush()

        log_entry.decision_status = "RESOLVED"
        await self.db.flush()

        logger.info("shadow_decision_resolved",
                    decision_id=str(decision_id),
                    realized_ev=realized_ev,
                    win=win_loss)

        return receipt
