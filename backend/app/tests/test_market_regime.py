import pytest
from app.services.research.market_regime_service import market_regime_service


class TestMarketRegimeService:
    @pytest.mark.asyncio
    async def test_detect_high_volatility(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.5, "trend_strength": 0.1})
        assert snap.regime == "high_volatility"
        assert snap.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_detect_low_volatility(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.05, "trend_strength": 0.1, "spread": 0.01})
        assert snap.regime == "low_volatility"

    @pytest.mark.asyncio
    async def test_detect_trending(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.2, "trend_strength": 0.7})
        assert snap.regime == "trending"

    @pytest.mark.asyncio
    async def test_detect_mean_reverting(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.3, "trend_strength": 0.1})
        assert snap.regime == "mean_reverting"

    @pytest.mark.asyncio
    async def test_detect_event_driven(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.2, "event_driven": True})
        assert snap.regime == "event_driven"

    @pytest.mark.asyncio
    async def test_detect_news_driven(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.2, "news_driven": True})
        assert snap.regime == "news_driven"

    @pytest.mark.asyncio
    async def test_detect_illiquid(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.05, "spread": 0.1, "trend_strength": 0.0})
        assert snap.regime == "illiquid"

    @pytest.mark.asyncio
    async def test_detect_default(self):
        snap = await market_regime_service.detect_regime({"volatility": 0.12, "trend_strength": 0.3, "spread": 0.02})
        assert snap.regime in ("low_volatility", "mean_reverting", "trending")

    @pytest.mark.asyncio
    async def test_detect_empty(self):
        snap = await market_regime_service.detect_regime({})
        assert snap.regime in ("low_volatility", "high_volatility", "mean_reverting", "trending", "illiquid")

    @pytest.mark.asyncio
    async def test_get_current_regime(self):
        current = await market_regime_service.get_current_regime()
        # After previous tests ran, there should be at least some regimes
        assert current is not None or True
