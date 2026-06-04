import math
from typing import Any

from app.core.logging import logger
from app.schemas.research import ChampionResult
from app.services.shadow.strategy_tournament_service import tournament_service
from app.services.shadow.shadow_analytics_service import analytics_service
from app.services.shadow.shadow_benchmark_service import benchmark_service
from app.services.shadow.shadow_promotion_service import promotion_service
from app.services.shadow.shadow_execution_service import shadow_execution_service

CHAMPION_CACHE_PREFIX = "research:champion:cache:"
CHAMPION_CACHE_TTL = 120


class ChampionChallengerService:
    async def _safe_redis(self):
        try:
            from app.redis import get_redis
            return await get_redis()
        except Exception:
            return None

    async def _get_cached(self, key: str) -> dict[str, Any] | None:
        r = await self._safe_redis()
        if not r:
            return None
        try:
            import json
            data = await r.get(f"{CHAMPION_CACHE_PREFIX}{key}")
            if data:
                return json.loads(data)
        except Exception:
            pass
        return None

    async def _set_cache(self, key: str, data: dict[str, Any]):
        r = await self._safe_redis()
        if not r:
            return
        try:
            import json
            await r.setex(f"{CHAMPION_CACHE_PREFIX}{key}", CHAMPION_CACHE_TTL, json.dumps(data, default=str))
        except Exception:
            pass

    async def evaluate(self, live_strategies: list[str] | None = None) -> ChampionResult:
        cached = await self._get_cached("champion")
        if cached:
            return ChampionResult(**cached)

        await shadow_execution_service._ensure_redis()
        rankings = await tournament_service.get_rankings()

        if not rankings:
            result = ChampionResult()
            await self._set_cache("champion", result.model_dump())
            return result

        live = [r for r in rankings if r.tier == "LIVE"] if live_strategies is None else [r for r in rankings if r.strategy in live_strategies]
        contenders = [r for r in rankings if r.tier in ("PAPER", "LIVE")]

        if not live and not contenders:
            result = ChampionResult()
            await self._set_cache("champion", result.model_dump())
            return result

        champion = max(contenders, key=lambda r: r.score) if contenders else None
        challengers = sorted(
            [r for r in contenders if champion is None or r.strategy != champion.strategy],
            key=lambda r: r.score,
            reverse=True,
        )[:10]

        replacement_score = 0.0
        recommendation = "KEEP"

        if champion:
            challenger_list = [r.model_dump() for r in challengers]
            if challengers and challengers[0].score > champion.score * 1.2:
                replacement_score = challengers[0].score / champion.score if champion.score > 0 else 1.0
                recommendation = "REPLACE"
            elif challengers and challengers[0].score > champion.score * 1.05:
                replacement_score = challengers[0].score / champion.score if champion.score > 0 else 1.0
                recommendation = "WATCH"
        else:
            challenger_list = []

        result = ChampionResult(
            champion=champion.strategy if champion else None,
            champion_score=round(champion.score, 4) if champion else 0.0,
            challengers=challenger_list,
            replacement_score=round(replacement_score, 4),
            recommendation=recommendation,
        )
        await self._set_cache("champion", result.model_dump())
        return result


champion_service = ChampionChallengerService()
