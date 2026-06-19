from app.domain.markets import InstrumentId, MarketResolution


class RegistryCache:
    def __init__(self):
        self._cache: dict[str, MarketResolution] = {}

    def _key(self, instrument: InstrumentId) -> str:
        return f"{instrument.venue}:{instrument.symbol}"

    def get(self, instrument: InstrumentId) -> MarketResolution | None:
        return self._cache.get(self._key(instrument))

    def set(self, instrument: InstrumentId, resolution: MarketResolution) -> None:
        self._cache[self._key(instrument)] = resolution

    def invalidate(self, instrument: InstrumentId) -> None:
        self._cache.pop(self._key(instrument), None)

    def clear(self) -> None:
        self._cache.clear()
