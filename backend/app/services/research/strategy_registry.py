import json
from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.research import StrategyMetadata

REGISTRY_HASH = "research:strategy:registry"


class StrategyRegistry:
    def __init__(self):
        self._local: dict[str, StrategyMetadata] = {}

    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def register(self, strategy_id: str, name: str, owner: str = "unknown", notes: str = "") -> StrategyMetadata:
        existing = self._local.get(strategy_id) or await self.get(strategy_id)
        if existing:
            return existing

        meta = StrategyMetadata(
            strategy_id=strategy_id,
            name=name,
            version=1,
            owner=owner,
            status="experimental",
            created_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        await self._persist(meta)
        logger.info("research_strategy_registered", strategy_id=strategy_id, name=name)
        return meta

    async def _persist(self, meta: StrategyMetadata):
        self._local[meta.strategy_id] = meta
        r = await self._safe_redis()
        if not r:
            return
        try:
            await r.hset(REGISTRY_HASH, meta.strategy_id, json.dumps(meta.model_dump(), default=str))
        except Exception as e:
            logger.warning("research_registry_save_failed", error=str(e))

    async def get(self, strategy_id: str) -> StrategyMetadata | None:
        r = await self._safe_redis()
        if r:
            try:
                data = await r.hget(REGISTRY_HASH, strategy_id)
                if data:
                    return StrategyMetadata(**json.loads(data))
            except Exception as e:
                logger.warning("research_registry_load_failed", error=str(e))
        return self._local.get(strategy_id)

    async def get_all(self) -> list[StrategyMetadata]:
        r = await self._safe_redis()
        if r:
            try:
                data = await r.hgetall(REGISTRY_HASH)
                if data:
                    results = []
                    for val in data.values():
                        try:
                            results.append(StrategyMetadata(**json.loads(val)))
                        except Exception:
                            pass
                    return results
            except Exception:
                pass
        return list(self._local.values())

    async def promote(self, strategy_id: str, new_status: str, notes: str = "") -> StrategyMetadata | None:
        meta = await self.get(strategy_id)
        if not meta:
            return None

        old_status = meta.status
        meta.status = new_status
        meta.promoted_at = datetime.now(timezone.utc).isoformat()
        if notes:
            meta.notes = notes
        await self._persist(meta)
        logger.info("research_strategy_promoted", strategy_id=strategy_id, from_status=old_status, to_status=new_status)
        return meta

    async def retire(self, strategy_id: str, successor: str | None = None, notes: str = "") -> StrategyMetadata | None:
        meta = await self.get(strategy_id)
        if not meta:
            return None

        old_status = meta.status
        meta.status = "retired"
        meta.retired_at = datetime.now(timezone.utc).isoformat()
        if successor:
            meta.successor = successor
        if notes:
            meta.notes = notes
        await self._persist(meta)
        logger.info("research_strategy_retired", strategy_id=strategy_id, from_status=old_status)
        return meta

    async def get_active(self, status: str | None = None) -> list[StrategyMetadata]:
        all_ = await self.get_all()
        if status:
            return [m for m in all_ if m.status == status]
        return [m for m in all_ if m.status != "retired"]

    async def get_history(self, strategy_id: str) -> list[StrategyMetadata]:
        all_ = await self.get_all()
        chain: list[StrategyMetadata] = []
        current = strategy_id
        visited = set()
        while current and current not in visited:
            visited.add(current)
            meta = next((m for m in all_ if m.strategy_id == current), None)
            if meta:
                chain.append(meta)
                current = meta.predecessor
            else:
                break
        chain.reverse()

        forward = []
        current = strategy_id
        visited2 = set()
        while current and current not in visited2:
            visited2.add(current)
            meta = next((m for m in all_ if m.strategy_id == current), None)
            if meta and meta.successor:
                forward.append(meta)
                current = meta.successor
            else:
                if meta:
                    forward.append(meta)
                break
        merged = list(dict.fromkeys(chain + forward))
        return merged


registry = StrategyRegistry()
