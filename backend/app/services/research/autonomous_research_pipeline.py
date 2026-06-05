import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.research_memory import ResearchReport, CandidateRecommendation, IncubationDecision
from app.services.research.research_memory import research_memory
from app.services.research.strategy_generator import strategy_generator
from app.services.research.market_regime_service import market_regime_service
from app.services.research.hypothesis_engine import hypothesis_engine
from app.services.evolution.population_service import population_service
from app.services.audit.audit_logger import emit as audit_emit
from app.services.control.control_plane import control_plane


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


class AutonomousResearchPipeline(SafeRedisMixin):
    REP_PREFIX = "research:reports"

    def __init__(self):
        self._local_reports: list[ResearchReport] = []

    async def run(self, market_data: dict | None = None) -> ResearchReport:
        await audit_emit("research.pipeline.start", "research", "pipeline", {})

        mode = await self._safe_read_execution_mode()
        if mode == "disabled":
            await audit_emit("research.pipeline.skipped", "research", "pipeline", {"reason": "disabled"})
            report = ResearchReport(report_id=f"rpt-{uuid.uuid4()[:8]}", generated_at=datetime.now(timezone.utc).isoformat())
            self._local_reports.append(report)
            return report

        # 1. Detect regime
        regime = await market_regime_service.detect_regime(market_data or {})
        regimes = [regime]

        # 2. Generate hypotheses
        hyp1 = hypothesis_engine.propose(
            title=f"Strategy performance during {regime.regime}",
            description=f"Analyze how strategies perform during {regime.regime} regimes",
            tags=[regime.regime, "regime_analysis"],
        )
        hyp2 = hypothesis_engine.propose(
            title="Signal source effectiveness",
            description="Compare effectiveness of different signal sources across regimes",
            tags=["signals", "effectiveness"],
        )
        hypotheses = [hyp1, hyp2]

        # 3. Generate candidates
        candidates: list[CandidateRecommendation] = []

        top = [{"strategy_id": "top-1", "archetype": "momentum", "generation": 3},
               {"strategy_id": "top-2", "archetype": "mean_reversion", "generation": 2}]
        mutated = await strategy_generator.mutate_top_performers(top)
        candidates.extend(mutated)

        champions = [{"strategy_id": "champ-1", "archetype": "trend", "generation": 5},
                     {"strategy_id": "champ-2", "archetype": "breakout", "generation": 4}]
        recombined = await strategy_generator.recombine_champions(champions)
        candidates.extend(recombined)

        contrarian = await strategy_generator.generate_contrarian()
        candidates.extend(contrarian)

        regime_candidates = await strategy_generator.generate_regime_specific(regime.regime)
        candidates.extend(regime_candidates)

        novel = await strategy_generator.generate_novel()
        candidates.extend(novel)

        # 4. Score candidates
        for c in candidates:
            c.incubation_ready = c.confidence >= 0.4

        # 5. Store findings
        for c in candidates:
            await audit_emit("candidate.generated", "research", "pipeline", {
                "candidate_id": c.candidate_id, "archetype": c.archetype,
            })

        report = ResearchReport(
report_id=f"rpt-{str(uuid.uuid4())[:8]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
            regimes=regimes,
            hypotheses=hypotheses,
            candidates=candidates,
            summary=f"Generated {len(candidates)} candidates under {regime.regime} regime",
        )
        self._local_reports.append(report)
        await self._safe_redis("rpush", self.REP_PREFIX, report.model_dump_json())
        await audit_emit("research.pipeline.completed", "research", "pipeline", {
            "report_id": report.report_id, "candidates": len(candidates),
        })
        return report

    async def get_reports(self) -> list[ResearchReport]:
        raw = await self._safe_redis("lrange", self.REP_PREFIX, 0, -1)
        if raw:
            try:
                return [ResearchReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_reports)

    async def get_latest_report(self) -> ResearchReport | None:
        reports = await self.get_reports()
        return reports[-1] if reports else None

    async def get_candidate_recommendations(self) -> list[CandidateRecommendation]:
        report = await self.get_latest_report()
        return report.candidates if report else []

    async def _safe_read_execution_mode(self) -> str:
        try:
            return await control_plane.get_execution_mode()
        except Exception:
            return "shadow"


pipeline = AutonomousResearchPipeline()