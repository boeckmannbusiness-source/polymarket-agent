from abc import ABC, abstractmethod

from app.domain.markets import InstrumentId, Market, MarketResolution


class MarketResolver(ABC):
    @abstractmethod
    async def resolve(self, instrument: InstrumentId) -> MarketResolution:
        ...
