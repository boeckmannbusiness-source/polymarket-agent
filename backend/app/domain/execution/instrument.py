from pydantic import BaseModel


class Instrument(BaseModel):
    venue: str
    symbol: str
    asset_identifier: str
    quote_asset: str
    metadata: dict | None = None
