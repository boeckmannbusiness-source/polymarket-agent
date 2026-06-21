from .registry import PriceResolverRegistry
from .venue_price_resolver import VenuePriceResolver

def bootstrap_price_resolvers():
    """
    Initialize the PriceResolverRegistry with venue-specific resolvers.
    """
    # For MVP, both use VenuePriceResolver which is venue-agnostic
    # in its interface but can be specialized per venue if needed.
    resolver = VenuePriceResolver()
    PriceResolverRegistry.register("jupiter", resolver)
    PriceResolverRegistry.register("polymarket", resolver)
