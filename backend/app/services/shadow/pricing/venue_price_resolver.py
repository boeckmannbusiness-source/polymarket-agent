from decimal import Decimal
from typing import Optional
from app.domain.assets import AssetResolution
from app.services.shadow.pricing.resolver import PriceResolver
from app.core.logging import logger


class VenuePriceResolver(PriceResolver):
    """Implementation of PriceResolver that uses venue-agnostic asset resolutions."""

    async def resolve_price(self, asset_resolution: AssetResolution) -> Optional[Decimal]:
        """
        Resolves the price based on the asset resolution.
        Initially, it may rely on the metadata or existing market data.
        """
        try:
            # In a real implementation, this would call external price feeds or venue APIs.
            # For the shadow layer, we might extract it from the resolution metadata or latest market snapshot.
            if asset_resolution.asset.metadata and "price" in asset_resolution.asset.metadata:
                return Decimal(str(asset_resolution.asset.metadata["price"]))

            # Fallback to a default if price is not available
            return None
        except Exception as e:
            logger.warning("price_resolution_failed", asset=asset_resolution.asset.asset_id.symbol, error=str(e))
            return None
