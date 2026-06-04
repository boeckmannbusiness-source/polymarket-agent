import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Fill
from app.services.portfolio_service import PortfolioService
from app.services.monitoring.event_stream_service import EventStreamService
from app.services.portfolio.portfolio_cache_service import PortfolioCacheService
from app.services.stream.event_normalizer import EventNormalizer
from app.services.alerts.alert_service import alert_service
from app.services.monitoring.latency_service import latency_tracker
from app.ws.manager import manager


class FillHandler:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_fill(self, fill: Fill):
        from app.services.control.control_plane import control_plane

        if fill.trade and fill.trade.agent_id and await control_plane.is_strategy_paused(fill.trade.agent_id):
            logger.warning("fill_for_paused_strategy", strategy=fill.trade.agent_id, fill_id=str(fill.id))

        if fill.market_id and await control_plane.is_market_paused(fill.market_id):
            logger.warning("fill_for_paused_market", market=fill.market_id, fill_id=str(fill.id))

        start = time.time()
        service = PortfolioService(self.db)
        await service.upsert_from_fill(fill)

        stream = EventStreamService()
        await stream.publish_fill_event(fill)

        cache = PortfolioCacheService()
        await cache.invalidate_on_fill()

        normalized = EventNormalizer.normalize_fill_event(fill)
        latency_tracker.record_fill_latency(str(fill.id), start)
        await manager.broadcast_event(normalized, channels=["fills", "portfolio", "trades"])

        await alert_service.evaluate(normalized)

        elapsed_ms = (time.time() - start) * 1000
        latency_tracker.record("fill_processing", elapsed_ms)
