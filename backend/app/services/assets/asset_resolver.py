from abc import ABC, abstractmethod
from app.domain.assets import AssetId, AssetResolution


class AssetResolver(ABC):
    @abstractmethod
    async def resolve(self, asset_id: AssetId) -> AssetResolution:
        pass
