import pytest
from app.schemas.evolution import FitnessScore
from app.services.evolution.fitness_calculator import fitness_calculator


class TestFitnessCalculator:
    def test_compute_defaults(self):
        f = fitness_calculator.compute()
        assert f.composite_fitness == 36.0

    def test_compute_positive_values(self):
        f = fitness_calculator.compute(sharpe=2.0, sortino=2.0, alpha=0.5, drawdown=0.1, confidence=0.9, health=90, promotion=1.0)
        assert f.sharpe_score == 80.0
        assert f.sortino_score == 80.0
        assert f.alpha_score == 50.0
        assert f.drawdown_score == 90.0
        assert f.confidence_score == 90.0
        assert f.health_score == 90.0
        assert f.promotion_score == 100.0

    def test_compute_clamping_sharpe(self):
        f = fitness_calculator.compute(sharpe=-3.0)
        assert f.sharpe_score == 0.0
        f2 = fitness_calculator.compute(sharpe=5.0)
        assert f2.sharpe_score == 100.0

    def test_compute_clamping_sortino(self):
        f = fitness_calculator.compute(sortino=-5.0)
        assert f.sortino_score == 0.0
        f2 = fitness_calculator.compute(sortino=10.0)
        assert f2.sortino_score == 100.0

    def test_compute_alpha_clamping(self):
        f = fitness_calculator.compute(alpha=-0.1)
        assert f.alpha_score == 0.0
        f2 = fitness_calculator.compute(alpha=2.0)
        assert f2.alpha_score == 100.0

    def test_compute_drawdown_clamping(self):
        f = fitness_calculator.compute(drawdown=1.5)
        assert f.drawdown_score == 0.0
        f2 = fitness_calculator.compute(drawdown=-0.5)
        assert f2.drawdown_score == 100.0

    def test_compute_health_clamping(self):
        f = fitness_calculator.compute(health=200)
        assert f.health_score == 100.0
        f2 = fitness_calculator.compute(health=-10)
        assert f2.health_score == 0.0

    def test_composite_weights(self):
        f = fitness_calculator.compute(sharpe=3.0, sortino=3.0, alpha=1.0, drawdown=0.0, confidence=1.0, health=100, promotion=1.0)
        # All max scores = 100 each
        # 100*0.25 + 100*0.15 + 100*0.10 + 100*0.20 + 100*0.05 + 100*0.15 + 100*0.10 = 25+15+10+20+5+15+10 = 100
        assert f.composite_fitness == 100.0

    def test_deterministic(self):
        f1 = fitness_calculator.compute(sharpe=1.0, sortino=0.5, alpha=0.2, drawdown=0.15)
        f2 = fitness_calculator.compute(sharpe=1.0, sortino=0.5, alpha=0.2, drawdown=0.15)
        assert f1.composite_fitness == f2.composite_fitness

    def test_score_bounds(self):
        scores = [
            fitness_calculator.compute(sharpe=-100).sharpe_score,
            fitness_calculator.compute(sortino=-100).sortino_score,
            fitness_calculator.compute(alpha=-100).alpha_score,
            fitness_calculator.compute(drawdown=100).drawdown_score,
            fitness_calculator.compute(confidence=-100).confidence_score,
            fitness_calculator.compute(health=-100).health_score,
            fitness_calculator.compute(promotion=-100).promotion_score,
        ]
        for s in scores:
            assert 0 <= s <= 100, f"Score {s} out of bounds"
