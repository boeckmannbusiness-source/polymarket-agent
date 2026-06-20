from typing import Dict
from app.domain.capabilities import VenueCapabilities, VenueCapability


class CapabilityRegistry:
    _instance = None
    _registry: Dict[str, VenueCapabilities] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CapabilityRegistry, cls).__new__(cls)
        return cls._instance

    def register(self, venue: str, capabilities: VenueCapabilities):
        self._registry[venue] = capabilities

    def get_capabilities(self, venue: str) -> VenueCapabilities | None:
        return self._registry.get(venue)


# Global registry instance
capability_registry = CapabilityRegistry()

# Default registrations
capability_registry.register("paper", VenueCapabilities(
    venue="paper",
    supports={
        VenueCapability.QUOTE,
        VenueCapability.SIMULATION,
        VenueCapability.EXECUTION,
        VenueCapability.MARKET_RESOLUTION,
    }
))

capability_registry.register("polymarket", VenueCapabilities(
    venue="polymarket",
    supports={
        VenueCapability.QUOTE,
        VenueCapability.EXECUTION,
        VenueCapability.MARKET_RESOLUTION,
        VenueCapability.REPLAY,
        VenueCapability.PORTFOLIO_FEEDBACK,
    }
))

capability_registry.register("live_jupiter", VenueCapabilities(
    venue="live_jupiter",
    supports={
        VenueCapability.QUOTE,
        VenueCapability.ROUTING,
        VenueCapability.TRANSACTION_BUILDING,
        VenueCapability.SIMULATION,
        VenueCapability.EXECUTION,
        VenueCapability.MULTI_HOP,
        VenueCapability.SLIPPAGE_MODEL,
        VenueCapability.REPLAY,
        VenueCapability.PORTFOLIO_FEEDBACK,
    }
))
