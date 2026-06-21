from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from app.domain.assets import AssetResolution


class PriceResolver(ABC):
    """Interface for resolving asset prices in the shadow layer."""

    @abstractmethod
    async def resolve_price(self, asset_resolution: AssetResolution) -> Optional[Decimal]:
        """Resolves the current price for a given asset resolution."""
        pass
