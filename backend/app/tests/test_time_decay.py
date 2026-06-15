import math

import pytest

from app.services.time_decay import TimeDecayService


class TestTimeDecayService:
    def test_decay_recency_at_zero(self):
        svc = TimeDecayService(half_life_hours=24)
        assert svc.decay_recency(0) == pytest.approx(1.0)

    def test_decay_recency_at_half_life(self):
        svc = TimeDecayService(half_life_hours=24)
        assert svc.decay_recency(24) == pytest.approx(0.5, rel=0.01)

    def test_decay_recency_at_two_half_lives(self):
        svc = TimeDecayService(half_life_hours=24)
        assert svc.decay_recency(48) == pytest.approx(0.25, rel=0.01)

    def test_decay_recency_monotonic_decreasing(self):
        svc = TimeDecayService(half_life_hours=24)
        for t in range(0, 200, 10):
            assert svc.decay_recency(t) >= svc.decay_recency(t + 1)

    def test_decay_recency_negative_input(self):
        svc = TimeDecayService(half_life_hours=24)
        assert svc.decay_recency(-1) == 1.0
        assert svc.decay_recency(-1e6) == 1.0

    def test_decay_recency_large_value_approaches_zero(self):
        svc = TimeDecayService(half_life_hours=24)
        result = svc.decay_recency(240)
        assert 0 < result < 0.01

    def test_decay_recency_never_below_zero(self):
        svc = TimeDecayService(half_life_hours=24)
        for t in range(0, 10000, 100):
            assert svc.decay_recency(t) >= 0.0

    def test_decay_frequency_zero(self):
        svc = TimeDecayService()
        assert svc.decay_frequency(0) == pytest.approx(0.0)

    def test_decay_frequency_increasing(self):
        svc = TimeDecayService()
        vals = [svc.decay_frequency(i) for i in range(0, 100, 5)]
        for i in range(len(vals) - 1):
            assert vals[i] <= vals[i + 1]

    def test_decay_frequency_clamps(self):
        svc = TimeDecayService()
        assert svc.decay_frequency(-1) == 0.0
        assert svc.decay_frequency(10) <= 1.0
        assert svc.decay_frequency(100) <= 1.0

    def test_decay_frequency_approaches_one(self):
        svc = TimeDecayService()
        for large in [100, 500, 1000]:
            val = svc.decay_frequency(large)
            assert val > 0.99
            assert val <= 1.0

    def test_deterministic_output(self):
        svc = TimeDecayService(half_life_hours=24)
        for _ in range(10):
            assert svc.decay_recency(12) == svc.decay_recency(12)
            assert svc.decay_frequency(5) == svc.decay_frequency(5)

    def test_custom_half_life(self):
        svc = TimeDecayService(half_life_hours=1)
        assert svc.decay_recency(1) == pytest.approx(0.5, rel=0.01)
        assert svc.decay_recency(2) == pytest.approx(0.25, rel=0.01)

    def test_decay_formula(self):
        svc = TimeDecayService(half_life_hours=24)
        lam = math.log(2) / 24
        expected = math.exp(-lam * 36)
        assert svc.decay_recency(36) == pytest.approx(expected)

    def test_custom_saturation_constant(self):
        svc = TimeDecayService(saturation_trades=20)
        assert svc.decay_frequency(10) == pytest.approx(1.0 - math.exp(-10 / 20), rel=0.01)
        assert svc.decay_frequency(20) == pytest.approx(1.0 - math.exp(-20 / 20), rel=0.01)
        assert svc.decay_frequency(10) < svc.decay_frequency(20)

    def test_saturation_default_from_config(self):
        svc = TimeDecayService()
        result = svc.decay_frequency(10)
        assert result == pytest.approx(1.0 - math.exp(-1.0), rel=0.01)
