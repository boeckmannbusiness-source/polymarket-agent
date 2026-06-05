import uuid
from datetime import datetime, timezone
from typing import Any

from app.schemas.research_memory import HypothesisRecord


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


class HypothesisEngine(SafeRedisMixin):
    HYP_PREFIX = "research:hypotheses"

    def __init__(self):
        self._local_hypotheses: list[HypothesisRecord] = []

    def propose(self, title: str, description: str, tags: list[str] | None = None) -> HypothesisRecord:
        hypothesis = HypothesisRecord(
            hypothesis_id=f"hyp-{str(uuid.uuid4())[:8]}",
            title=title,
            description=description,
            status="PROPOSED",
            confidence=0.0,
            evidence=[],
            tags=tags or [],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._local_hypotheses.append(hypothesis)
        return hypothesis

    async def start_testing(self, hypothesis_id: str) -> HypothesisRecord | None:
        return await self._update_status(hypothesis_id, "TESTING")

    async def validate(self, hypothesis_id: str, evidence: list[str] | None = None, confidence: float | None = None) -> HypothesisRecord | None:
        hypotheses = await self._get_all()
        for h in hypotheses:
            if h.hypothesis_id == hypothesis_id:
                h.status = "VALIDATED"
                if evidence:
                    h.evidence.extend(evidence)
                if confidence is not None:
                    h.confidence = confidence
                h.updated_at = datetime.now(timezone.utc).isoformat()
                await self._sync(hypotheses)
                return h
        return None

    async def reject(self, hypothesis_id: str, reason: str | None = None) -> HypothesisRecord | None:
        h = await self._update_status(hypothesis_id, "REJECTED")
        if h and reason:
            h.evidence.append(reason)
        return h

    async def archive(self, hypothesis_id: str) -> HypothesisRecord | None:
        return await self._update_status(hypothesis_id, "ARCHIVED")

    async def get_all(self) -> list[HypothesisRecord]:
        return await self._get_all()

    async def get_by_status(self, status: str) -> list[HypothesisRecord]:
        all_h = await self._get_all()
        return [h for h in all_h if h.status == status]

    async def _update_status(self, hypothesis_id: str, status: str) -> HypothesisRecord | None:
        hypotheses = await self._get_all()
        for h in hypotheses:
            if h.hypothesis_id == hypothesis_id:
                h.status = status
                h.updated_at = datetime.now(timezone.utc).isoformat()
                await self._sync(hypotheses)
                return h
        return None

    async def _get_all(self) -> list[HypothesisRecord]:
        raw = await self._safe_redis("lrange", self.HYP_PREFIX, 0, -1)
        if raw:
            try:
                return [HypothesisRecord.model_validate_json(r) for r in raw]
            except Exception:
                pass
        return list(self._local_hypotheses)

    async def _sync(self, hypotheses: list[HypothesisRecord]) -> None:
        self._local_hypotheses = hypotheses
        for h in hypotheses:
            await self._safe_redis("rpush", self.HYP_PREFIX, h.model_dump_json())


hypothesis_engine = HypothesisEngine()