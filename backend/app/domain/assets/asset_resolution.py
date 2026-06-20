from pydantic import BaseModel
from .asset import Asset


class AssetResolution(BaseModel):
    asset: Asset
    source: str
    confidence: float
    resolution_metadata: dict = {}
