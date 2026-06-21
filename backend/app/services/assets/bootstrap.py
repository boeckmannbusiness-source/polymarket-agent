from .asset_registry import AssetRegistry
from .translators import JupiterAssetTranslator, PolymarketAssetTranslator
from app.core.logging import logger


def bootstrap_asset_registry() -> None:
    """Initialize and validate the global AssetRegistry."""
    logger.info("bootstrapping_asset_registry")

    # Register default translators
    AssetRegistry.register_resolver("jupiter", JupiterAssetTranslator())
    AssetRegistry.register_resolver("polymarket", PolymarketAssetTranslator())

    # Validate integrity
    _validate_registry()

    logger.info("asset_registry_bootstrapped", venues=AssetRegistry.list_venues())


def _validate_registry() -> None:
    """Ensure all registered venues have resolvers."""
    venues = AssetRegistry.list_venues()
    if not venues:
        logger.warning("asset_registry_empty_after_bootstrap")
        return

    for venue in venues:
        if not AssetRegistry.get_resolver(venue):
            raise RuntimeError(f"AssetRegistry integrity error: Venue '{venue}' registered but resolver missing.")
