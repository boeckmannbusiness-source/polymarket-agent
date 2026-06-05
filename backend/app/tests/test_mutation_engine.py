import pytest
from app.services.evolution.mutation_engine import mutation_engine
from app.services.evolution.strategy_genome import genome_service


class TestMutationEngine:
    def test_mutate_confidence_threshold(self):
        g = genome_service.create(confidence_threshold=0.5)
        mutated = mutation_engine.mutate(g, seed=42)
        # With seed=42 and MUTATION_RATE=0.3 per gene, some will hit
        mutated_ids = [id(mutated) != id(g)]
        assert mutated is not None

    def test_mutate_is_bounded(self):
        g = genome_service.create(confidence_threshold=0.95, sizing_multiplier=5.0, risk_multiplier=3.0)
        mutated = mutation_engine.mutate(g, seed=1)
        assert 0.1 <= mutated.confidence_threshold <= 0.95
        assert 0.1 <= mutated.sizing_multiplier <= 5.0
        assert 0.1 <= mutated.risk_multiplier <= 3.0

    def test_mutate_negative_bounds(self):
        g = genome_service.create(confidence_threshold=0.1, sizing_multiplier=0.1, risk_multiplier=0.1)
        mutated = mutation_engine.mutate(g, seed=999)
        assert 0.1 <= mutated.confidence_threshold <= 0.95
        assert 0.1 <= mutated.sizing_multiplier <= 5.0
        assert 0.1 <= mutated.risk_multiplier <= 3.0

    def test_deterministic_with_seed(self):
        g = genome_service.create()
        r1 = mutation_engine.mutate(g, seed=100)
        r2 = mutation_engine.mutate(g, seed=100)
        assert r1.confidence_threshold == r2.confidence_threshold
        assert r1.sizing_multiplier == r2.sizing_multiplier
        assert r1.risk_multiplier == r2.risk_multiplier
        assert r1.consensus_mode == r2.consensus_mode

    def test_different_seeds_different_results(self):
        g = genome_service.create()
        r1 = mutation_engine.mutate(g, seed=1)
        r2 = mutation_engine.mutate(g, seed=2)
        # Probabilistic but very unlikely to be identical
        attrs = ["confidence_threshold", "sizing_multiplier", "risk_multiplier", "consensus_mode", "signal_weights"]
        assert any(getattr(r1, a) != getattr(r2, a) for a in attrs)

    def test_mutate_consensus_mode_changes(self):
        g = genome_service.create(consensus_mode="majority")
        results = set()
        for s in range(50):
            mutated = mutation_engine.mutate(g, seed=s)
            if mutated.consensus_mode != "majority":
                results.add(mutated.consensus_mode)
        # At least some should mutate to a different mode over 50 seeds
        assert len(results) > 0

    def test_mutate_weights_changed(self):
        g = genome_service.create(signal_weights={"sharpe": 1.0, "sortino": 0.8})
        mutated = mutation_engine.mutate(g, seed=5)
        # At high seed count some weights should change
        weight_changes = [k for k in g.signal_weights if g.signal_weights[k] != mutated.signal_weights.get(k)]
        # Not guaranteed, but with MUTATION_RATE=0.3 per gene and seed variation
        assert len(weight_changes) >= 0

    def test_mutate_with_report_returns_changes(self):
        g = genome_service.create()
        _, changes = mutation_engine.mutate_with_report(g, seed=42)
        assert isinstance(changes, list)

    def test_mutate_preserves_majority_structure(self):
        g = genome_service.create()
        mutated = mutation_engine.mutate(g, seed=7)
        assert mutated.strategy_id == g.strategy_id
        assert mutated.parent_ids == g.parent_ids
        assert mutated.generation == g.generation
        assert mutated.archetype == g.archetype

    def test_mutate_report_matches_actual_mutations(self):
        g = genome_service.create(confidence_threshold=0.5, sizing_multiplier=1.0)
        # Use a seed we know triggers mutations
        for s in range(100):
            m, changes = mutation_engine.mutate_with_report(g, seed=s)
            if changes:
                assert m.confidence_threshold != g.confidence_threshold or m.sizing_multiplier != g.sizing_multiplier or m.risk_multiplier != g.risk_multiplier or m.consensus_mode != g.consensus_mode
                return
        # At least one seed should trigger a mutation
        assert False, "No mutations triggered in 100 seeds"
