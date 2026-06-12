from pydantic import BaseModel, Field
from typing import Any


class HeliusTokenTransfer(BaseModel):
    mint: str = Field(..., min_length=32, max_length=44)
    token_amount: float | None = None
    token_account: str | None = None
    from_user_account: str | None = None
    to_user_account: str | None = None


class HeliusTransaction(BaseModel):
    type: str = Field(..., pattern=r"^(SWAP|TRANSFER|UNKNOWN)$")
    signature: str = Field(..., min_length=64, max_length=128)
    timestamp: int | None = None
    slot: int | None = None
    fee: int | None = None
    description: str | None = None
    tokenTransfers: list[HeliusTokenTransfer] = Field(default_factory=list)
    nativeTransfers: list[dict[str, Any]] = Field(default_factory=list)
    accountData: list[dict[str, Any]] = Field(default_factory=list)
    source: str | None = None
    accounts: list[str] = Field(default_factory=list)
