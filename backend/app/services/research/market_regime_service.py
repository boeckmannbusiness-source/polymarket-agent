from datetime import datetime, timezone
from typing import Any

from app.schemas.research_memory import RegimeSnapshot
from app.services.research.research_memory import research_memory


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


class MarketRegimeService(SafeRedisMixin):
    async def detect_regime(self, market_data: dict | None = None) -> RegimeSnapshot:
        vol = market_data.get("volatility", 0.0) if market_data else 0.0
        trend = market_data.get("trend_strength", 0.0) if market_data else 0.0
        volume = market_data.get("volume_ratio", 1.0) if market_data else 1.0
        spread = market_data.get("spread", 0.0) if market_data else 0.0
        event_flag = market_data.get("event_driven", False) if market_data else False
        news_flag = market_data.get("news_driven", False) if market_data else False

        if event_flag:
            regime = "event_driven"
        elif news_flag:
            regime = "news_driven"
        elif vol > 0.4:
            regime = "high_volatility"
        elif vol < 0.1 and spread > 0.05:
            regime = "illiquid"
        elif vol < 0.15:
            regime = "low_volatility"
        elif trend > 0.6:
            regime = "trending"
        elif trend < -0.6:
            regime = "trending"
        elif abs(trend) < 0.2 and vol > 0.2:
            regime = "mean_reverting"
        else:
            regime = "low_volatility"

        indicators = {
            "volatility": round(vol, 4),
            "trend_strength": round(trend, 4),
            "volume_ratio": round(volume, 4),
            "spread": round(spread, 4),
        }

        snapshot = RegimeSnapshot(
            regime=regime,
            confidence=self._calculate_confidence(regime, indicators),
            indicators=indicators,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        await research_memory.record_regime(snapshot)
        return snapshot

    def _calculate_confidence(self, regime: str, indicators: dict[str, float]) -> float:
        vol = indicators.get("volatility", 0.0)
        trend = indicators.get("trend_strength", 0.0)
        if regime == "high_volatility":
            return min(1.0, vol * 2.0)
        elif regime == "low_volatility":
            return min(1.0, 1.0 - vol * 5.0)
        elif regime == "trending":
            return min(1.0, abs(trend) * 1.5)
        elif regime == "mean_reverting":
            return min(1.0, (1.0 - abs(trend)) * 0.8 + vol * 0.5)
        elif regime in ("event_driven", "news_driven"):
            return 0.85
        elif regime == "illiquid":
            return min(1.0, indicators.get("spread", 0.0) * 10.0)
        return 0.5

    async def get_regime_history(self) -> list[RegimeSnapshot]:
        return await research_memory.get_regimes()

    async def get_current_regime(self) -> RegimeSnapshot | None:
        regimes = await research_memory.get_regimes()
        return regimes[-1] if regimes else None


market_regime_service = MarketRegimeService()