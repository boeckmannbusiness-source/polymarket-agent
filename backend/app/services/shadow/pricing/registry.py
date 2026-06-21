from typing import Dict, Optional
from app.services.shadow.pricing.resolver import PriceResolver

class PriceResolverRegistry:
    _resolvers: Dict[str, PriceResolver] = {}

    @classmethod
    def register(cls, venue: str, resolver: PriceResolver) -> None:
        cls._resolvers[venue] = resolver

    @classmethod
    def get(cls, venue: str) -> Optional[PriceResolver]:
        return cls._resolvers.get(venue)

    @classmethod
    def clear(cls):
        cls._resolvers = {}
