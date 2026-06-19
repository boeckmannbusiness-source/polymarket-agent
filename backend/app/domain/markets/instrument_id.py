from pydantic import BaseModel


class InstrumentId(BaseModel):
    venue: str
    symbol: str
    quote_asset: str = "USDC"
