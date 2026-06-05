from typing import Any

from app.schemas.evolution import LineageNode


class StrategyLineageService:
    def build_tree(self, lineage: list[LineageNode]) -> list[dict[str, Any]]:
        node_map = {n.strategy_id: n for n in lineage}
        for node in lineage:
            for pid in node.parent_ids:
                parent = node_map.get(pid)
                if parent and node.strategy_id not in parent.child_ids:
                    parent.child_ids.append(node.strategy_id)
        roots = [n for n in lineage if not n.parent_ids]
        return [self._node_to_dict(r) for r in roots]

    def _node_to_dict(self, node: LineageNode) -> dict[str, Any]:
        return {
            "strategy_id": node.strategy_id,
            "generation": node.generation,
            "archetype": node.archetype,
            "status": node.status,
            "fitness": node.fitness,
            "children": [],
        }

    def get_promotion_history(self, lineage: list[LineageNode]) -> list[dict[str, Any]]:
        history = []
        for node in lineage:
            history.append({
                "strategy_id": node.strategy_id,
                "generation": node.generation,
                "status": node.status,
                "fitness": node.fitness,
            })
        return sorted(history, key=lambda x: x["generation"], reverse=True)

    def get_retirement_history(self, lineage: list[LineageNode]) -> list[dict[str, Any]]:
        return [n.model_dump() for n in lineage if n.status == "RETIRED"]


lineage_service = StrategyLineageService()