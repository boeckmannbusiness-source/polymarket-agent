import pytest
from app.services.evolution.strategy_genome import genome_service
from app.schemas.evolution import StrategyGenome


class TestStrategyGenomeService:
    def test_create_default_genome(self):
        g = genome_service.create()
        assert g.strategy_id
        assert g.parent_ids == []
        assert g.generation == 0
        assert g.archetype == "exploration"
        assert g.confidence_threshold == 0.5
        assert g.sizing_multiplier == 1.0
        assert g.risk_multiplier == 1.0
        assert g.consensus_mode == "majority"
        assert g.created_at

    def test_create_with_custom_params(self):
        g = genome_service.create(
            archetype="momentum",
            parent_ids=["p1", "p2"],
            generation=2,
            confidence_threshold=0.75,
            sizing_multiplier=1.5,
            risk_multiplier=0.8,
            consensus_mode="weighted_confidence",
        )
        assert g.archetype == "momentum"
        assert g.parent_ids == ["p1", "p2"]
        assert g.generation == 2
        assert g.confidence_threshold == 0.75
        assert g.sizing_multiplier == 1.5
        assert g.risk_multiplier == 0.8
        assert g.consensus_mode == "weighted_confidence"

    def test_clone_from_generation_increment(self):
        parent = genome_service.create(generation=3)
        child = genome_service.clone_from(parent)
        assert child.generation == 4
        assert parent.strategy_id in child.parent_ids
        assert child.strategy_id != parent.strategy_id

    def test_clone_from_preserves_weights(self):
        parent = genome_service.create(signal_weights={"alpha": 2.0, "beta": 1.5})
        child = genome_service.clone_from(parent)
        assert child.signal_weights["alpha"] == 2.0
        assert child.signal_weights["beta"] == 1.5

    def test_to_dict_roundtrip(self):
        g = genome_service.create(archetype="trend_following")
        d = genome_service.to_dict(g)
        restored = genome_service.from_dict(d)
        assert restored.strategy_id == g.strategy_id
        assert restored.archetype == g.archetype
        assert restored.confidence_threshold == g.confidence_threshold

    def test_deterministic_serialization(self):
        g = genome_service.create()
        d1 = genome_service.to_dict(g)
        d2 = genome_service.to_dict(g)
        assert d1 == d2
        assert d1["strategy_id"] == d2["strategy_id"]

    def test_default_signal_weights_present(self):
        g = genome_service.create()
        for k in ["sharpe", "sortino", "alpha", "drawdown", "win_rate", "profit_factor"]:
            assert k in g.signal_weights

    def test_new_id_provided_to_clone(self):
        parent = genome_service.create()
        child = genome_service.clone_from(parent, new_id="custom-id")
        assert child.strategy_id == "custom-id"
