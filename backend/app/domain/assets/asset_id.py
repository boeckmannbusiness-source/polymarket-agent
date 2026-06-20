from pydantic import BaseModel, ConfigDict


class AssetId(BaseModel):
    model_config = ConfigDict(frozen=True)

    venue: str
    symbol: str
    canonical_id: str
    quote_asset: str
