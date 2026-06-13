from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
from typing import Any


class EventEnvelope(BaseModel):
    event_id: str = Field(..., min_length=25, max_length=25, pattern=r"^evt_")
    event_type: str = Field(..., min_length=3, max_length=64)
    source: str = Field(..., min_length=1, max_length=64)
    timestamp: str = Field(..., min_length=20, max_length=30)
    correlation_id: str = Field(..., min_length=25, max_length=25, pattern=r"^corr_")
    data: dict[str, Any]

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                raise ValueError("timestamp must be timezone-aware (UTC)")
            return v
        except (ValueError, TypeError):
            raise ValueError(f"invalid ISO 8601 timestamp: {v}")


class MarketDataPayload(BaseModel):
    wallet_address: str = Field(..., min_length=32, max_length=44)
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    size_usd: float = Field(..., gt=0)
    price_usd: float = Field(..., gt=0)
    tx_signature: str = Field(..., min_length=64, max_length=88)
    source_dex: str | None = Field(None, max_length=32)
    slot: int | None = Field(None, gt=0)

    @field_validator("wallet_address", "mint_address", "tx_signature")
    @classmethod
    def validate_base58(cls, v: str) -> str:
        allowed = set("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz123456789")
        if not all(c in allowed for c in v):
            raise ValueError(f"invalid base58 character in {v[:8]}...")
        return v


class WalletTradePayload(BaseModel):
    wallet_address: str = Field(..., min_length=32, max_length=44)
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    size_usd: float = Field(..., gt=0)
    price_usd: float = Field(..., gt=0)
    tx_signature: str = Field(..., min_length=64, max_length=88)
    research_score: float = Field(..., ge=0.0, le=1.0)
    total_trades_observed: int = Field(..., ge=0)
    win_rate_observed: float = Field(..., ge=0.0, le=1.0)


class SignalGeneratedPayload(BaseModel):
    signal_id: str = Field(..., min_length=25, max_length=25, pattern=r"^sig_")
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    direction: str = Field(..., pattern=r"^(long)$")
    confidence: float = Field(..., ge=0.0, le=1.0)
    trigger: str = Field(
        ...,
        pattern=r"^(coordinated_buy_3_wallets|high_score_entry|early_entry_trending)$",
    )
    wallet_addresses: list[str] = Field(..., min_length=1, max_length=20)
    detected_price_usd: float = Field(..., gt=0)
    signal_timestamp: str = Field(..., min_length=20, max_length=30)
    strategy: str = Field(..., min_length=1, max_length=64)


class TradeRequestPayload(BaseModel):
    request_id: str = Field(..., min_length=25, max_length=25, pattern=r"^req_")
    signal_id: str = Field(..., min_length=25, max_length=25, pattern=r"^sig_")
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    direction: str = Field(..., pattern=r"^(long)$")
    size_usd: float = Field(..., gt=0)
    entry_price_usd: float = Field(..., gt=0)
    stop_loss_usd: float = Field(..., gt=0)
    take_profit_usd: float = Field(..., gt=0)
    max_hold_hours: int = Field(..., ge=1, le=720)
    simulated_slippage: float = Field(0.01, ge=0.0, le=0.1)
    simulated_fee: float = Field(0.005, ge=0.0, le=0.1)
    is_shadow: bool = Field(True)
    strategy: str = Field(..., min_length=1, max_length=64)


class ShadowPositionOpenedPayload(BaseModel):
    position_id: str = Field(..., min_length=25, max_length=25, pattern=r"^pos_")
    request_id: str = Field(..., min_length=25, max_length=25, pattern=r"^req_")
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    direction: str = Field(..., pattern=r"^(long)$")
    entry_price_usd: float = Field(..., gt=0)
    size_usd: float = Field(..., gt=0)
    gross_entry_cost: float = Field(..., gt=0)
    simulated_slippage_cost: float = Field(..., ge=0.0)
    simulated_fee_cost: float = Field(..., ge=0.0)
    net_entry_cost: float = Field(..., gt=0)
    stop_loss_usd: float | None = Field(None, gt=0)
    take_profit_usd: float | None = Field(None, gt=0)
    max_hold_hours: int = Field(72, ge=1, le=720)
    status: str = Field("open", pattern=r"^(open)$")
    entry_timestamp: str = Field(..., min_length=20, max_length=30)


class ShadowPositionClosedPayload(BaseModel):
    position_id: str = Field(..., min_length=25, max_length=25, pattern=r"^pos_")
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    direction: str = Field(..., pattern=r"^(long)$")
    entry_price_usd: float = Field(..., gt=0)
    exit_price_usd: float = Field(..., gt=0)
    size_usd: float = Field(..., gt=0)
    gross_pnl_usd: float
    simulated_slippage: float = Field(0.01, ge=0.0, le=0.1)
    simulated_fee: float = Field(0.005, ge=0.0, le=0.1)
    net_pnl_usd: float
    status: str = Field("closed", pattern=r"^(closed)$")
    exit_reason: str = Field(..., pattern=r"^(take_profit|stop_loss|expired)$")
    entry_timestamp: str = Field(..., min_length=20, max_length=30)
    exit_timestamp: str = Field(..., min_length=20, max_length=30)
    hold_hours: float = Field(..., gt=0)
    strategy: str | None = Field(None, max_length=64)


class SolanaTradeDetectedPayload(BaseModel):
    wallet_address: str = Field(..., min_length=32, max_length=44)
    mint_address: str = Field(..., min_length=32, max_length=44)
    token_symbol: str | None = Field(None, min_length=2, max_length=10)
    side: str = Field(..., pattern=r"^(buy|sell)$")
    size_usd: float = Field(..., gt=0)
    price_usd: float | None = Field(None, ge=0)
    tx_signature: str = Field(..., min_length=64, max_length=128)
    slot: int | None = Field(None, gt=0)
    source_dex: str | None = Field(None, max_length=32)
    block_time: str = Field(..., min_length=20, max_length=30)
    trade_id: str = Field(..., min_length=32, max_length=64)


# Event type → payload model mapping
EVENT_PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    "market:data": MarketDataPayload,
    "wallet:trade": WalletTradePayload,
    "signal:generated": SignalGeneratedPayload,
    "trade:request": TradeRequestPayload,
    "shadow:position.opened": ShadowPositionOpenedPayload,
    "shadow:position.closed": ShadowPositionClosedPayload,
    "solana:trade:detected": SolanaTradeDetectedPayload,
}
