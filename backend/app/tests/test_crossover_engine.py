import pytest
from app.services.evolution.crossover_engine import crossover_engine
from app.services.evolution.strategy_genome import genome_service


class TestCrossoverEngine:
    def test_crossover_creates_child_genome(self):
        a = genome_service.create(archetype="momentum", confidence_threshold=0.3)
        b = genome_service.create(archetype="mean_reversion", confidence_threshold=0.8)
        child, report = crossover_engine.crossover(a, b, seed=1)
        assert child.strategy_id
        assert child.generation == 1
        assert a.strategy_id in child.parent_ids
        assert b.strategy_id in child.parent_ids

    def test_crossover_inherits_traits(self):
        a = genome_service.create(archetype="momentum")
        b = genome_service.create(archetype="mean_reversion")
        child, report = crossover_engine.crossover(a, b, seed=1)
        assert report.inherited_traits
        assert "confidence_threshold" in report.inherited_traits
        assert "sizing_multiplier" in report.inherited_traits
        assert "risk_multiplier" in report.inherited_traits
        assert "consensus_mode" in report.inherited_traits

    def test_crossover_report_contains_parents(self):
        a = genome_service.create()
        b = genome_service.create()
        _, report = crossover_engine.crossover(a, b, seed=1)
        assert report.parent_a_id == a.strategy_id
        assert report.parent_b_id == b.strategy_id
        assert report.crossover_type == "uniform"

    def test_crossover_deterministic(self):
        a = genome_service.create(archetype="momentum")
        b = genome_service.create(archetype="trend", confidence_threshold=0.7)
        c1, r1 = crossover_engine.crossover(a, b, seed=42)
        c2, r2 = crossover_engine.crossover(a, b, seed=42)
        assert c1.confidence_threshold == c2.confidence_threshold
        assert c1.sizing_multiplier == c2.sizing_multiplier
        assert c1.risk_multiplier == c2.risk_multiplier
        assert c1.consensus_mode == c2.consensus_mode
        assert c1.signal_weights == c2.signal_weights
        assert r1.inherited_traits == r2.inherited_traits

    def test_crossover_varying_seeds(self):
        a = genome_service.create(archetype="momentum", confidence_threshold=0.3, sizing_multiplier=0.5)
        b = genome_service.create(archetype="mean_reversion", confidence_threshold=0.8, sizing_multiplier=2.0)
        results = set()
        for seed in range(20):
            child, _ = crossover_engine.crossover(a, b, seed=seed)
            results.add((child.confidence_threshold, child.sizing_multiplier))
        assert len(results) > 1, "Different seeds should produce at least some variation"

    def test_crossover_signal_weights_combine(self):
        a = genome_service.create(signal_weights={"alpha": 2.0, "beta": 0.5})
        b = genome_service.create(signal_weights={"beta": 1.5, "gamma": 1.0})
        child, _ = crossover_engine.crossover(a, b, seed=10)
        for k in ["alpha", "beta", "gamma"]:
            assert k in child.signal_weights

    def test_crossover_parent_generation_tracked(self):
        a = genome_service.create(generation=5)
        b = genome_service.create(generation=3)
        child, _ = crossover_engine.crossover(a, b, seed=1)
        assert child.generation == 6

    def test_crossover_report_child_id_matches(self):
        a = genome_service.create()
        b = genome_service.create()
        child, report = crossover_engine.crossover(a, b, seed=1)
        assert report.child_id == child.strategy_id

    def test_crossover_archetype_format(self):
        a = genome_service.create(archetype="momentum")
        b = genome_service.create(archetype="volatility")
        child, _ = crossover_engine.crossover(a, b, seed=1)
        assert child.archetype == "cx:momentum:volatility"
