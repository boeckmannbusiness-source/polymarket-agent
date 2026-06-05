import pytest
from app.services.research.strategy_candidate_service import candidate_service
from app.services.research.strategy_lineage_service import lineage_service
from app.schemas.evolution import LineageNode, Candidate, StrategyGenome
from datetime import datetime, timezone


class TestCandidateService:
    def test_validate_transition_forward(self):
        assert candidate_service.validate_transition("EXPERIMENTAL", "SHADOW") is True
        assert candidate_service.validate_transition("SHADOW", "PAPER") is True
        assert candidate_service.validate_transition("PAPER", "LIVE") is True
        assert candidate_service.validate_transition("LIVE", "RETIRED") is True

    def test_validate_transition_skip(self):
        assert candidate_service.validate_transition("EXPERIMENTAL", "PAPER") is False
        assert candidate_service.validate_transition("SHADOW", "LIVE") is False

    def test_validate_transition_from_retired(self):
        assert candidate_service.validate_transition("RETIRED", "LIVE") is False

    def test_validate_transition_to_retired_any(self):
        assert candidate_service.validate_transition("EXPERIMENTAL", "RETIRED") is True
        assert candidate_service.validate_transition("SHADOW", "RETIRED") is True
        assert candidate_service.validate_transition("PAPER", "RETIRED") is True
        assert candidate_service.validate_transition("LIVE", "RETIRED") is True

    def test_get_next_status(self):
        assert candidate_service.get_next_status("EXPERIMENTAL") == "SHADOW"
        assert candidate_service.get_next_status("SHADOW") == "PAPER"
        assert candidate_service.get_next_status("PAPER") == "LIVE"
        assert candidate_service.get_next_status("LIVE") == "RETIRED"
        assert candidate_service.get_next_status("RETIRED") is None

    def test_get_next_status_invalid(self):
        assert candidate_service.get_next_status("INVALID") is None

    def test_invalid_transition_bad_status(self):
        assert candidate_service.validate_transition("INVALID", "SHADOW") is False

    async def test_transition_async(self, monkeypatch):
        class FakePop:
            async def update_candidate_status(self, cid, status):
                pass

        genome = StrategyGenome(strategy_id="test-candidate", archetype="test", created_at=datetime.now(timezone.utc).isoformat())
        candidate = Candidate(candidate_id="test-candidate", genome=genome, status="EXPERIMENTAL", created_at=datetime.now(timezone.utc).isoformat(), updated_at=datetime.now(timezone.utc).isoformat())
        result = await candidate_service.transition(candidate, "SHADOW", FakePop())
        assert result is not None
        assert result.status == "SHADOW"

    async def test_transition_invalid_async(self, monkeypatch):
        genome = StrategyGenome(strategy_id="test-candidate-2", archetype="test", created_at=datetime.now(timezone.utc).isoformat())
        candidate = Candidate(candidate_id="test-candidate-2", genome=genome, status="EXPERIMENTAL", created_at=datetime.now(timezone.utc).isoformat(), updated_at=datetime.now(timezone.utc).isoformat())
        result = await candidate_service.transition(candidate, "LIVE", None)
        assert result is None


class TestLineageService:
    def test_build_tree_roots(self):
        nodes = [
            LineageNode(strategy_id="root", generation=0, parent_ids=[], child_ids=[], archetype="momentum", status="active"),
            LineageNode(strategy_id="child", generation=1, parent_ids=["root"], child_ids=[], archetype="trend", status="active"),
        ]
        tree = lineage_service.build_tree(nodes)
        assert len(tree) == 1
        assert tree[0]["strategy_id"] == "root"

    def test_get_promotion_history(self):
        nodes = [
            LineageNode(strategy_id="s1", generation=0, parent_ids=[], child_ids=[], archetype="a", status="LIVE", fitness=90.0),
            LineageNode(strategy_id="s2", generation=1, parent_ids=["s1"], child_ids=[], archetype="b", status="SHADOW", fitness=80.0),
        ]
        hist = lineage_service.get_promotion_history(nodes)
        assert len(hist) == 2
        assert hist[0]["generation"] >= hist[1]["generation"]

    def test_get_retirement_history(self):
        nodes = [
            LineageNode(strategy_id="s1", generation=0, parent_ids=[], child_ids=[], archetype="a", status="RETIRED", fitness=50.0),
            LineageNode(strategy_id="s2", generation=1, parent_ids=[], child_ids=[], archetype="b", status="active", fitness=90.0),
        ]
        retired = lineage_service.get_retirement_history(nodes)
        assert len(retired) == 1
        assert retired[0]["strategy_id"] == "s1"
