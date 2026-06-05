from app.schemas.evolution import FitnessScore


class FitnessCalculator:
    def compute(
        self,
        sharpe: float = 0.0,
        sortino: float = 0.0,
        alpha: float = 0.0,
        drawdown: float = 0.0,
        confidence: float = 0.0,
        health: float = 0.0,
        promotion: float = 0.0,
    ) -> FitnessScore:
        clamped_sharpe = max(-2.0, min(3.0, sharpe))
        sharpe_score = (clamped_sharpe + 2.0) / 5.0 * 100.0

        clamped_sortino = max(-2.0, min(3.0, sortino))
        sortino_score = (clamped_sortino + 2.0) / 5.0 * 100.0

        alpha_score = max(0.0, min(100.0, alpha * 100.0))

        drawdown_score = max(0.0, min(100.0, (1.0 - drawdown) * 100.0))

        confidence_score = max(0.0, min(100.0, confidence * 100.0))

        health_score = max(0.0, min(100.0, health))

        promotion_score = max(0.0, min(100.0, promotion * 100.0))

        composite = (
            sharpe_score * 0.25
            + sortino_score * 0.15
            + alpha_score * 0.10
            + drawdown_score * 0.20
            + confidence_score * 0.05
            + health_score * 0.15
            + promotion_score * 0.10
        )

        return FitnessScore(
            strategy_id="",
            sharpe_score=round(sharpe_score, 2),
            sortino_score=round(sortino_score, 2),
            alpha_score=round(alpha_score, 2),
            drawdown_score=round(drawdown_score, 2),
            confidence_score=round(confidence_score, 2),
            health_score=round(health_score, 2),
            promotion_score=round(promotion_score, 2),
            composite_fitness=round(composite, 2),
        )


fitness_calculator = FitnessCalculator()