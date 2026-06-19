from decimal import Decimal
from pydantic import BaseModel


class TransactionInstruction(BaseModel):
    instruction_type: str  # SWAP | TRANSFER | ROUTE_HOP
    source_asset: str
    target_asset: str
    amount: Decimal
    metadata: dict | None = None
