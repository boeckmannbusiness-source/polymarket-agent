from pydantic import BaseModel, Field
from .asset_id import AssetId
from .asset_metadata import AssetMetadata


class Asset(BaseModel):
    asset_id: AssetId
    decimals: int
    metadata: AssetMetadata
    tags: list[str] = Field(default_factory=list)
