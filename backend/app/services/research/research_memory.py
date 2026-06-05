from datetime import datetime, timezone
from typing import Any

from app.schemas.research_memory import ResearchMemoryEntry, HypothesisRecord, RegimeSnapshot
from app.schemas.intelligence import PortfolioReviewReport, StressTestResult, ResilienceReport, InvestmentCommitteeReport
from app.services.audit.audit_logger import emit as audit_emit


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


class ResearchMemory(SafeRedisMixin):
    MEM_PREFIX = "research:memory"
    HYP_PREFIX = "research:hypotheses"
    REG_PREFIX = "research:regimes"

    def __init__(self):
        self._local_memory: list[ResearchMemoryEntry] = []
        self._local_hypotheses: list[HypothesisRecord] = []
        self._local_regimes: list[RegimeSnapshot] = []

    async def store(self, entry: ResearchMemoryEntry) -> None:
        self._local_memory.append(entry)
        await self._safe_redis("rpush", self.MEM_PREFIX, entry.model_dump_json())
        await audit_emit("research.memory.created", "research", "memory", {
            "entry_id": entry.entry_id, "entry_type": entry.entry_type,
        })

    async def get_memory(self, entry_type: str | None = None, tags: list[str] | None = None) -> list[ResearchMemoryEntry]:
        raw = await self._safe_redis("lrange", self.MEM_PREFIX, 0, -1)
        entries = []
        if raw:
            try:
                entries = [ResearchMemoryEntry.model_validate_json(r) for r in raw]
            except Exception:
                entries = list(self._local_memory)
        else:
            entries = list(self._local_memory)

        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        if tags:
            entries = [e for e in entries if any(t in e.tags for t in tags)]
        return entries

    async def add_hypothesis(self, hypothesis: HypothesisRecord) -> None:
        self._local_hypotheses.append(hypothesis)
        await self._safe_redis("rpush", self.HYP_PREFIX, hypothesis.model_dump_json())
        await audit_emit("hypothesis.created", "research", "hypothesis", {
            "hypothesis_id": hypothesis.hypothesis_id, "title": hypothesis.title,
        })

    async def update_hypothesis(self, hypothesis_id: str, status: str | None = None, evidence: list[str] | None = None, confidence: float | None = None) -> HypothesisRecord | None:
        hypotheses = await self.get_hypotheses()
        for h in hypotheses:
            if h.hypothesis_id == hypothesis_id:
                if status:
                    h.status = status
                if evidence:
                    h.evidence.extend(evidence)
                if confidence is not None:
                    h.confidence = confidence
                h.updated_at = datetime.now(timezone.utc).isoformat()
                await self._sync_hypotheses(hypotheses)
                await audit_emit("hypothesis.updated", "research", "hypothesis", {
                    "hypothesis_id": hypothesis_id, "status": status,
                })
                return h
        return None

    async def get_hypotheses(self) -> list[HypothesisRecord]:
        raw = await self._safe_redis("lrange", self.HYP_PREFIX, 0, -1)
        if raw:
            try:
                return [HypothesisRecord.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_hypotheses)

    async def record_regime(self, snapshot: RegimeSnapshot) -> None:
        self._local_regimes.append(snapshot)
        await self._safe_redis("rpush", self.REG_PREFIX, snapshot.model_dump_json())
        await audit_emit("regime.changed", "research", "regime", {
            "regime": snapshot.regime, "confidence": snapshot.confidence,
        })

    async def get_regimes(self) -> list[RegimeSnapshot]:
        raw = await self._safe_redis("lrange", self.REG_PREFIX, 0, -1)
        if raw:
            try:
                return [RegimeSnapshot.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_regimes)

    async def get_current_regime(self) -> RegimeSnapshot | None:
        regimes = await self.get_regimes()
        return regimes[-1] if regimes else None

    async def _sync_hypotheses(self, hypotheses: list[HypothesisRecord]) -> None:
        self._local_hypotheses = hypotheses
        serialized = [h.model_dump_json() for h in hypotheses]
        for item in serialized:
            await self._safe_redis("rpush", self.HYP_PREFIX, item)


    # ── Portfolio Review storage ──────────────────────────────

    async def store_portfolio_review(self, review: PortfolioReviewReport) -> None:
        await self._safe_redis("rpush", "research:portfolio_reviews", review.model_dump_json())

    async def get_portfolio_reviews(self) -> list[PortfolioReviewReport]:
        raw = await self._safe_redis("lrange", "research:portfolio_reviews", 0, -1)
        if raw:
            try:
                return [PortfolioReviewReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return []

    # ── Stress Test storage ──────────────────────────────────

    async def store_stress_test_result(self, result: StressTestResult) -> None:
        await self._safe_redis("rpush", "research:stress_tests", result.model_dump_json())

    async def get_stress_test_results(self) -> list[StressTestResult]:
        raw = await self._safe_redis("lrange", "research:stress_tests", 0, -1)
        if raw:
            try:
                return [StressTestResult.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return []

    # ── Resilience Report storage ───────────────────────────

    async def store_resilience_report(self, report: ResilienceReport) -> None:
        await self._safe_redis("rpush", "research:resilience_reports", report.model_dump_json())

    async def get_resilience_reports(self) -> list[ResilienceReport]:
        raw = await self._safe_redis("lrange", "research:resilience_reports", 0, -1)
        if raw:
            try:
                return [ResilienceReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return []

    # ── Committee Report storage ───────────────────────────

    async def store_committee_report(self, report: InvestmentCommitteeReport) -> None:
        await self._safe_redis("rpush", "research:committee_reports", report.model_dump_json())

    async def get_committee_reports(self) -> list[InvestmentCommitteeReport]:
        raw = await self._safe_redis("lrange", "research:committee_reports", 0, -1)
        if raw:
            try:
                return [InvestmentCommitteeReport.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return []


research_memory = ResearchMemory()