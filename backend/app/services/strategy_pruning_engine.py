from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.core.logging import logger
from app.services.edge_reality_engine import EdgeRealityEngine
from app.services.overfitting_detector import OverfittingDetector
from app.services.survivability_simulator import SurvivabilitySimulator
from app.services.capital_efficiency_engine import CapitalEfficiencyEngine


@dataclass
class StrategyDecision:
    status: str  # "KEEP" | "REDUCE" | "DISABLE"
    confidence: float
    capital_recommendation: str
    reason: str
    classification: str = ""  # "REAL_ALPHA" | "WEAK_EDGE" | "OVERFITTED" | "LOSING_SYSTEM"


class StrategyPruningEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def decide(self, strategy_name: str) -> StrategyDecision:
        edge_engine = EdgeRealityEngine(self.db)
        overfit_detector = OverfittingDetector(self.db)
        survivability = SurvivabilitySimulator(self.db)
        efficiency_engine = CapitalEfficiencyEngine(self.db)

        edge = await edge_engine.compute_edge(strategy_name, days=60)
        overfit = await overfit_detector.detect(strategy_name)
        survival = await survivability.simulate(strategy_name, days=30, simulations=500)
        efficiency = await efficiency_engine.compute(strategy_name)

        reasons = []
        classification = "WEAK_EDGE"

        if survival.probability_of_ruin > 0.5:
            classification = "LOSING_SYSTEM"
            return StrategyDecision(
                status="DISABLE",
                confidence=0.9,
                capital_recommendation="ZERO",
                reason=f"probability_of_ruin_{survival.probability_of_ruin:.1%}_exceeds_50%",
                classification=classification,
            )

        if edge.total_trades < 5:
            return StrategyDecision(
                status="REDUCE",
                confidence=0.5,
                capital_recommendation="MINIMAL",
                reason="insufficient_trade_data_for_decision",
                classification="WEAK_EDGE",
            )

        positive_edge = edge.expectancy > 0
        low_overfit = overfit.score < 0.3
        positive_survival = survival.expected_return > 0
        stable_efficiency = efficiency.score > 0

        reasons.append(f"expectancy={edge.expectancy:.4f}")
        reasons.append(f"overfit_score={overfit.score:.2f}")
        reasons.append(f"survival_return={survival.expected_return:.4f}")
        reasons.append(f"efficiency={efficiency.score:.4f}")

        if positive_edge and low_overfit and positive_survival and stable_efficiency:
            classification = "REAL_ALPHA"
            capital_rec = "FULL"
            if edge.confidence_score > 0.7 and survival.probability_of_ruin < 0.1:
                return StrategyDecision(
                    status="KEEP",
                    confidence=edge.confidence_score,
                    capital_recommendation="HIGH",
                    reason="; ".join(reasons) + "; strong_edge_confirmed",
                    classification=classification,
                )
            return StrategyDecision(
                status="KEEP",
                confidence=edge.confidence_score,
                capital_recommendation=capital_rec,
                reason="; ".join(reasons) + "; positive_edge_low_overfit",
                classification=classification,
            )

        if overfit.score > 0.6 or (edge.expectancy <= 0 and edge.total_trades >= 20):
            classification = "OVERFITTED" if overfit.score > 0.6 else "LOSING_SYSTEM"
            return StrategyDecision(
                status="DISABLE",
                confidence=max(overfit.score, 0.7),
                capital_recommendation="ZERO",
                reason="; ".join(reasons) + "; disabling_due_to_overfit_or_negative_edge",
                classification=classification,
            )

        if not positive_survival or not positive_edge:
            classification = "WEAK_EDGE"
            return StrategyDecision(
                status="REDUCE",
                confidence=0.6,
                capital_recommendation="REDUCED",
                reason="; ".join(reasons) + "; mixed_signals_reducing_capital",
                classification=classification,
            )

        classification = "WEAK_EDGE"
        return StrategyDecision(
            status="REDUCE",
            confidence=0.5,
            capital_recommendation="MINIMAL",
            reason="; ".join(reasons) + "; unclear_signals_minimal_exposure",
            classification=classification,
        )

    async def decide_all(self) -> dict[str, StrategyDecision]:
        from app.models.strategy import StrategyConfigRecord
        result = await self.db.execute(
            select(StrategyConfigRecord).where(StrategyConfigRecord.enabled == True)
        )
        records = list(result.scalars().all())
        decisions = {}
        for record in records:
            decisions[record.strategy_name] = await self.decide(record.strategy_name)
        return decisions
