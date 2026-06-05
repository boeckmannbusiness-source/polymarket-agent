import uuid
import random
from datetime import datetime, timezone

from app.schemas.evolution import StrategyGenome, Candidate
from app.schemas.research_memory import CandidateRecommendation
from app.services.evolution.strategy_genome import genome_service
from app.services.evolution.fitness_calculator import fitness_calculator


class StrategyGenerator:
    async def mutate_top_performers(self, top_strategies: list[dict], count: int = 3) -> list[CandidateRecommendation]:
        recs = []
        for s in top_strategies[:count]:
            genome = genome_service.create(
                archetype=f"mutated:{s.get('archetype', 'unknown')}",
                parent_ids=[s.get("strategy_id", "")],
                generation=(s.get("generation", 0) or 0) + 1,
                confidence_threshold=round(random.uniform(0.3, 0.8), 2),
                sizing_multiplier=round(random.uniform(0.5, 2.0), 2),
                risk_multiplier=round(random.uniform(0.3, 1.5), 2),
            )
            recs.append(CandidateRecommendation(
                candidate_id=genome.strategy_id,
                strategy_id=genome.strategy_id,
                archetype=genome.archetype,
                confidence=round(random.uniform(0.5, 0.9), 2),
                novelty_score=round(random.uniform(0.3, 0.7), 2),
                diversity_score=round(random.uniform(0.3, 0.8), 2),
                incubation_ready=True,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
        return recs

    async def recombine_champions(self, champions: list[dict]) -> list[CandidateRecommendation]:
        recs = []
        if len(champions) < 2:
            return recs
        pairs = list(zip(champions[:-1], champions[1:]))
        for a, b in pairs[:3]:
            genome = genome_service.create(
                archetype=f"recombined:{a.get('archetype', 'a')}:{b.get('archetype', 'b')}",
                parent_ids=[a.get("strategy_id", ""), b.get("strategy_id", "")],
                generation=max(a.get("generation", 0) or 0, b.get("generation", 0) or 0) + 1,
                confidence_threshold=round(random.uniform(0.3, 0.8), 2),
                sizing_multiplier=round(random.uniform(0.5, 2.0), 2),
                risk_multiplier=round(random.uniform(0.3, 1.5), 2),
            )
            recs.append(CandidateRecommendation(
                candidate_id=genome.strategy_id,
                strategy_id=genome.strategy_id,
                archetype=genome.archetype,
                confidence=round(random.uniform(0.4, 0.8), 2),
                novelty_score=round(random.uniform(0.4, 0.8), 2),
                diversity_score=round(random.uniform(0.4, 0.9), 2),
                incubation_ready=True,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
        return recs

    async def generate_contrarian(self, count: int = 2) -> list[CandidateRecommendation]:
        recs = []
        for _ in range(count):
            genome = genome_service.create(
                archetype="contrarian",
                confidence_threshold=round(random.uniform(0.4, 0.7), 2),
                sizing_multiplier=round(random.uniform(0.3, 1.0), 2),
                risk_multiplier=round(random.uniform(0.5, 1.5), 2),
                consensus_mode="weighted_confidence",
            )
            recs.append(CandidateRecommendation(
                candidate_id=genome.strategy_id,
                strategy_id=genome.strategy_id,
                archetype="contrarian",
                confidence=round(random.uniform(0.3, 0.6), 2),
                novelty_score=round(random.uniform(0.6, 1.0), 2),
                diversity_score=round(random.uniform(0.6, 1.0), 2),
                incubation_ready=True,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
        return recs

    async def generate_regime_specific(self, regime: str, count: int = 2) -> list[CandidateRecommendation]:
        archetype_map = {
            "trending": "trend_following",
            "mean_reverting": "mean_reversion",
            "high_volatility": "volatility_breakout",
            "low_volatility": "range_trading",
            "event_driven": "event_driven",
            "news_driven": "news_reactive",
            "illiquid": "liquidity_provision",
        }
        base = archetype_map.get(regime, "exploration")
        recs = []
        for _ in range(count):
            genome = genome_service.create(archetype=f"regime:{base}")
            recs.append(CandidateRecommendation(
                candidate_id=genome.strategy_id,
                strategy_id=genome.strategy_id,
                archetype=genome.archetype,
                confidence=round(random.uniform(0.5, 0.8), 2),
                novelty_score=round(random.uniform(0.4, 0.8), 2),
                diversity_score=round(random.uniform(0.3, 0.7), 2),
                incubation_ready=True,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
        return recs

    async def generate_novel(self, count: int = 2) -> list[CandidateRecommendation]:
        novel_archetypes = ["ml_sentiment", "cross_market_arb", "volatility_curve", "liquidity_gradient", "orderflow_imbalance"]
        recs = []
        for _ in range(count):
            arch = random.choice(novel_archetypes)
            genome = genome_service.create(archetype=f"novel:{arch}")
            recs.append(CandidateRecommendation(
                candidate_id=genome.strategy_id,
                strategy_id=genome.strategy_id,
                archetype=genome.archetype,
                confidence=round(random.uniform(0.2, 0.5), 2),
                novelty_score=round(random.uniform(0.8, 1.0), 2),
                diversity_score=round(random.uniform(0.7, 1.0), 2),
                incubation_ready=True,
                generated_at=datetime.now(timezone.utc).isoformat(),
            ))
        return recs


strategy_generator = StrategyGenerator()