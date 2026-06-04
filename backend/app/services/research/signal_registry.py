import json
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.signals import ResearchSignal, RegistryEntry

SIGNAL_HASH = "research:signal:registry"
SIGNAL_LIST = "research:signal:ids"
MAX_SIGNALS = 500


class SignalRegistry:
    def __init__(self):
        self._local: dict[str, RegistryEntry] = {}

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def register(self, signal: ResearchSignal, quality_score: float = 0.0) -> RegistryEntry:
        now = datetime.now(timezone.utc).isoformat()
        entry = RegistryEntry(
            signal_id=signal.signal_id,
            agent_id=signal.agent_id,
            agent_name=signal.agent_name,
            market_id=signal.market_id,
            direction=signal.direction,
            outcome=signal.outcome,
            confidence=signal.confidence,
            quality_score=round(quality_score, 2),
            lifecycle="generated",
            promotion_state="none",
            created_at=signal.created_at or now,
            updated_at=now,
        )
        self._local[signal.signal_id] = entry

        r = await self._safe_redis()
        if r:
            try:
                entry_data = entry.model_dump()
                entry_data["evidence"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in signal.evidence]
                entry_data["rationale"] = signal.rationale
                await r.hset(SIGNAL_HASH, signal.signal_id, json.dumps(entry_data, default=str))
                await r.lpush(SIGNAL_LIST, signal.signal_id)
                await r.ltrim(SIGNAL_LIST, 0, MAX_SIGNALS - 1)
            except Exception as e:
                logger.warning("signal_registry_save_failed", error=str(e))

        logger.info("signal_registered", signal_id=signal.signal_id, agent=signal.agent_id)
        return entry

    async def update_lifecycle(self, signal_id: str, lifecycle: str, promotion_state: str = ""):
        entry = self._local.get(signal_id)
        if not entry:
            r = await self._safe_redis()
            if r:
                try:
                    data = await r.hget(SIGNAL_HASH, signal_id)
                    if data:
                        raw = json.loads(data)
                        entry = RegistryEntry(**raw)
                except Exception:
                    return None

        if not entry:
            return None

        entry.lifecycle = lifecycle
        if promotion_state:
            entry.promotion_state = promotion_state
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        self._local[signal_id] = entry

        r = await self._safe_redis()
        if r:
            try:
                raw = json.loads(await r.hget(SIGNAL_HASH, signal_id) or "{}")
                raw["lifecycle"] = lifecycle
                if promotion_state:
                    raw["promotion_state"] = promotion_state
                raw["updated_at"] = entry.updated_at
                await r.hset(SIGNAL_HASH, signal_id, json.dumps(raw, default=str))
            except Exception:
                pass
        return entry

    async def get(self, signal_id: str) -> RegistryEntry | None:
        local = self._local.get(signal_id)
        if local:
            return local

        r = await self._safe_redis()
        if r:
            try:
                data = await r.hget(SIGNAL_HASH, signal_id)
                if data:
                    return RegistryEntry(**json.loads(data))
            except Exception:
                pass
        return None

    async def get_all(self, lifecycle: str | None = None) -> list[RegistryEntry]:
        r = await self._safe_redis()
        results: list[RegistryEntry] = []
        if r:
            try:
                data = await r.hgetall(SIGNAL_HASH)
                for val in data.values():
                    try:
                        entry = RegistryEntry(**json.loads(val))
                        if lifecycle is None or entry.lifecycle == lifecycle:
                            results.append(entry)
                    except Exception:
                        pass
                return results
            except Exception:
                pass
        results = list(self._local.values())
        if lifecycle:
            results = [e for e in results if e.lifecycle == lifecycle]
        return results

    async def get_stats(self) -> dict[str, Any]:
        all_ = await self.get_all()
        total = len(all_)
        approved = sum(1 for e in all_ if e.lifecycle == "consensus_approved")
        rejected = sum(1 for e in all_ if e.lifecycle == "consensus_rejected")
        pending = sum(1 for e in all_ if e.lifecycle in ("generated", "scored", "meta_reviewed"))
        avg_conf = sum(e.confidence for e in all_) / total if total > 0 else 0.0
        avg_qual = sum(e.quality_score for e in all_) / total if total > 0 else 0.0
        return {
            "total_signals": total,
            "approved_count": approved,
            "rejected_count": rejected,
            "pending_count": pending,
            "avg_confidence": round(avg_conf, 4),
            "avg_quality": round(avg_qual, 2),
        }

    async def get_agent_counts(self) -> list[dict[str, Any]]:
        all_ = await self.get_all()
        by_agent: dict[str, dict[str, Any]] = {}
        for e in all_:
            if e.agent_id not in by_agent:
                by_agent[e.agent_id] = {"agent_id": e.agent_id, "agent_name": e.agent_name, "total": 0, "approved": 0, "rejected": 0}
            by_agent[e.agent_id]["total"] += 1
            if e.lifecycle == "consensus_approved":
                by_agent[e.agent_id]["approved"] += 1
            elif e.lifecycle == "consensus_rejected":
                by_agent[e.agent_id]["rejected"] += 1
        return list(by_agent.values())

    async def reset(self):
        self._local.clear()
        r = await self._safe_redis()
        if r:
            try:
                await r.delete(SIGNAL_HASH, SIGNAL_LIST)
            except Exception:
                pass

    async def count(self) -> int:
        return len(await self.get_all())


signal_registry = SignalRegistry()