from app.domain.markets import InstrumentId, Market, MarketResolution


class MarketRegistry:
    _resolvers: dict[str, "MarketResolver"] = {}

    @classmethod
    def register_resolver(cls, venue: str, resolver: "MarketResolver") -> None:
        cls._resolvers[venue] = resolver

    @classmethod
    def get_resolver(cls, venue: str) -> "MarketResolver | None":
        return cls._resolvers.get(venue)

    @classmethod
    async def resolve(cls, instrument: InstrumentId) -> MarketResolution:
        resolver = cls._resolvers.get(instrument.venue)
        if resolver:
            return await resolver.resolve(instrument)
        return MarketResolution(
            instrument=instrument,
            source="fallback",
            confidence=0.0,
        )

    @classmethod
    def has_venue(cls, venue: str) -> bool:
        return venue in cls._resolvers
