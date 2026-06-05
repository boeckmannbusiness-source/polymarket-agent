import json
from datetime import datetime, timezone
from typing import Any

from app.services.evolution.strategy_genome import genome_service
from app.schemas.evolution import StrategyGenome, FitnessScore, Candidate, PopulationEntry, LineageNode


class SafeRedisMixin:
    async def _safe_redis(self, method: str, *args, **kwargs) -> Any:
        try:
            from app.services.redis import redis_service
            redis = await redis_service.get_client() if hasattr(redis_service, 'get_client') else redis_service.redis
            if redis is None:
                return None
            func = getattr(redis, method, None)
            if func is None:
                return None
            if hasattr(func, '__call__'):
                return await func(*args, **kwargs)
            return None
        except Exception:
            return None


class PopulationService(SafeRedisMixin):
    POP_PREFIX = "evolution:population"
    LINEAGE_PREFIX = "evolution:lineage"
    GEN_PREFIX = "evolution:generations"
    CANDIDATE_PREFIX = "evolution:candidate"
    CHAMPION_SET = "evolution:champions"

    def __init__(self):
        self._local_candidates: dict[str, Candidate] = {}
        self._local_population: list[PopulationEntry] = []
        self._local_lineage: list[LineageNode] = []
        self._local_generations: list[dict[str, Any]] = []
        self._local_champions: set[str] = set()

    async def add_candidate(self, candidate: Candidate) -> None:
        self._local_candidates[candidate.candidate_id] = candidate
        key = f"{self.CANDIDATE_PREFIX}:{candidate.candidate_id}"
        data = candidate.model_dump_json()
        redis_ok = await self._safe_redis("set", key, data)
        if redis_ok is not None:
            await self._update_population(candidate)
            await self._update_lineage(candidate)

    async def update_candidate_fitness(self, candidate_id: str, fitness: FitnessScore) -> None:
        if candidate_id in self._local_candidates:
            self._local_candidates[candidate_id].fitness = fitness
            self._local_candidates[candidate_id].updated_at = datetime.now(timezone.utc).isoformat()
        key = f"{self.CANDIDATE_PREFIX}:{candidate_id}"
        raw = await self._safe_redis("get", key)
        if raw:
            try:
                data = json.loads(raw)
                data["fitness"] = json.loads(fitness.model_dump_json())
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self._safe_redis("set", key, json.dumps(data))
            except Exception:
                pass

    async def update_candidate_status(self, candidate_id: str, status: str) -> None:
        if candidate_id in self._local_candidates:
            self._local_candidates[candidate_id].status = status
            self._local_candidates[candidate_id].updated_at = datetime.now(timezone.utc).isoformat()
        key = f"{self.CANDIDATE_PREFIX}:{candidate_id}"
        raw = await self._safe_redis("get", key)
        if raw:
            try:
                data = json.loads(raw)
                data["status"] = status
                data["updated_at"] = datetime.now(timezone.utc).isoformat()
                await self._safe_redis("set", key, json.dumps(data))
            except Exception:
                pass

    async def register_champion(self, strategy_id: str) -> None:
        self._local_champions.add(strategy_id)
        await self._safe_redis("sadd", self.CHAMPION_SET, strategy_id)

    async def get_champions(self) -> list[str]:
        raw = await self._safe_redis("smembers", self.CHAMPION_SET)
        if raw:
            return list(raw)
        return list(self._local_champions)

    async def get_candidate(self, candidate_id: str) -> Candidate | None:
        if candidate_id in self._local_candidates:
            return self._local_candidates[candidate_id]
        key = f"{self.CANDIDATE_PREFIX}:{candidate_id}"
        raw = await self._safe_redis("get", key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            genome_data = data.get("genome")
            genome = StrategyGenome(**genome_data) if genome_data else None
            fitness_data = data.get("fitness")
            fitness = FitnessScore(**fitness_data) if fitness_data else None
            candidate = Candidate(
                candidate_id=data.get("candidate_id", candidate_id),
                genome=genome,
                status=data.get("status", "EXPERIMENTAL"),
                created_at=data.get("created_at", ""),
                updated_at=data.get("updated_at", ""),
                fitness=fitness,
            )
            self._local_candidates[candidate_id] = candidate
            return candidate
        except Exception:
            return None

    async def get_candidates(self) -> list[Candidate]:
        pattern = f"{self.CANDIDATE_PREFIX}:*"
        keys = await self._safe_redis("keys", pattern)
        if keys:
            result = []
            for key in keys:
                raw = await self._safe_redis("get", key)
                if raw:
                    try:
                        data = json.loads(raw)
                        genome_data = data.get("genome")
                        genome = StrategyGenome(**genome_data) if genome_data else None
                        fitness_data = data.get("fitness")
                        fitness = FitnessScore(**fitness_data) if fitness_data else None
                        result.append(Candidate(
                            candidate_id=data.get("candidate_id", ""),
                            genome=genome,
                            status=data.get("status", ""),
                            created_at=data.get("created_at", ""),
                            updated_at=data.get("updated_at", ""),
                            fitness=fitness,
                        ))
                    except Exception:
                        continue
            return result
        return list(self._local_candidates.values())

    async def get_population(self) -> list[PopulationEntry]:
        members = await self._safe_redis("smembers", self.POP_PREFIX)
        if members:
            result = []
            for m in members:
                try:
                    data = json.loads(m)
                    result.append(PopulationEntry(**data))
                except Exception:
                    continue
            return result
        return list(self._local_population)

    async def get_lineage(self) -> list[LineageNode]:
        members = await self._safe_redis("smembers", self.LINEAGE_PREFIX)
        if members:
            result = []
            for m in members:
                try:
                    data = json.loads(m)
                    result.append(LineageNode(**data))
                except Exception:
                    continue
            return result
        return list(self._local_lineage)

    async def get_generations(self) -> list[dict[str, Any]]:
        raw = await self._safe_redis("get", self.GEN_PREFIX)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return []
        return list(self._local_generations)

    async def record_generation(self, generation_data: dict[str, Any]) -> None:
        self._local_generations.append(generation_data)
        existing = await self.get_generations()
        if not isinstance(existing, list):
            existing = []
        existing.append(generation_data)
        await self._safe_redis("set", self.GEN_PREFIX, json.dumps(existing))

    async def _update_population(self, candidate: Candidate) -> None:
        if not candidate.genome:
            return
        entry = PopulationEntry(
            strategy_id=candidate.candidate_id,
            generation=candidate.genome.generation,
            archetype=candidate.genome.archetype,
            status="active",
            fitness=candidate.fitness.composite_fitness if candidate.fitness else 0.0,
            created_at=candidate.created_at,
        )
        self._local_population.append(entry)
        await self._safe_redis("sadd", self.POP_PREFIX, entry.model_dump_json())

    async def _update_lineage(self, candidate: Candidate) -> None:
        if not candidate.genome:
            return
        node = LineageNode(
            strategy_id=candidate.candidate_id,
            generation=candidate.genome.generation,
            parent_ids=candidate.genome.parent_ids,
            child_ids=[],
            archetype=candidate.genome.archetype,
            status=candidate.status,
            fitness=candidate.fitness.composite_fitness if candidate.fitness else 0.0,
        )
        self._local_lineage.append(node)
        await self._safe_redis("sadd", self.LINEAGE_PREFIX, node.model_dump_json())

    async def _redis_client(self):
        try:
            from app.services.redis import redis_service
            redis = await redis_service.get_client() if hasattr(redis_service, 'get_client') else redis_service.redis
            return redis
        except Exception:
            return None


population_service = PopulationService()