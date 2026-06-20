from app.domain.capabilities import VenueCapabilities
from .capability_registry import capability_registry


class CapabilityResolver:
    def resolve(self, venue: str) -> VenueCapabilities:
        caps = capability_registry.get_capabilities(venue)
        if caps is None:
            # Default to no capabilities if venue not found, or raise?
            # Issue says: "Must never instantiate adapters. Read-only only."
            return VenueCapabilities(venue=venue, supports=set())
        return caps
