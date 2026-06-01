from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.risk_service import RiskService
from app.services.global_risk_guard import GlobalRiskGuard
from app.core.logging import logger


@dataclass
class ValidationResult:
    approved: bool
    reasons: list[str]
    risk_result: object | None = None
    exposure_result: object | None = None


class ValidationEngine:
    """Unified entry point for trade validation.
    Wraps RiskService (confidence, daily loss, cooldown) and
    GlobalRiskGuard (exposure limits, position count).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk_service = RiskService(db)
        self.global_risk_guard = GlobalRiskGuard(db)

    async def validate_trade(
        self,
        market_id: UUID | None,
        side: str,
        size: float | None,
        confidence: float | None,
        agent_id: str | None = None,
        outcome: str = "YES",
        proposed_price: float = 0.5,
    ) -> ValidationResult:
        reasons = []

        # 1. RiskService checks (confidence, daily loss, cooldown, basic exposure)
        risk_result = await self.risk_service.validate_trade(
            market_id=market_id,
            side=side,
            size=size,
            confidence=confidence,
            agent_id=agent_id,
        )
        if not risk_result.approved:
            reasons.append(risk_result.reason)

        # 2. GlobalRiskGuard checks (hard exposure limits, position count, market concentration)
        exposure_result = await self.global_risk_guard.check_exposure(
            market_id=str(market_id) if market_id else "",
            outcome=outcome,
            proposed_size=size or 0,
            proposed_price=proposed_price,
        )
        if not exposure_result.approved:
            reasons.append(exposure_result.reason)

        approved = len(reasons) == 0

        if not approved:
            logger.warning(
                "validation_engine_rejected",
                market_id=str(market_id),
                side=side,
                confidence=confidence,
                reasons=reasons,
            )

        return ValidationResult(
            approved=approved,
            reasons=reasons,
            risk_result=risk_result,
            exposure_result=exposure_result,
        )
