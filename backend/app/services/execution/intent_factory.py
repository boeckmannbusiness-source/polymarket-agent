from decimal import Decimal
from typing import Optional
import uuid
from app.domain.execution import ExecutionIntent, Instrument
from app.models import Trade


class ExecutionIntentFactory:
    """Factory for constructing venue-neutral execution intents."""

    @staticmethod
    def create_from_trade(
        trade: Trade,
        engine_type: str,
        side: Optional[str] = None,
        quantity: Optional[Decimal] = None,
        limit_price: Optional[Decimal] = None,
        metadata: Optional[dict] = None
    ) -> ExecutionIntent:
        """
        Builds an ExecutionIntent from a Trade model.
        Decouples the intent from venue-specific outcome semantics.
        """
        # Venue-neutral asset identification
        asset_in = getattr(trade, "asset_in", str(trade.market_id) if trade.market_id else "")
        asset_out = getattr(trade, "asset_out", "USDC")

        instrument = Instrument(
            venue=engine_type,
            symbol=str(trade.market_id) if trade.market_id else "",
            asset_identifier=asset_in,
            quote_asset=asset_out,
            # metadata is venue-neutral; specific outcomes go to compat_outcome
            metadata=None
        )

        intent = ExecutionIntent(
            instrument=instrument,
            side=side or trade.side,
            quantity=quantity or Decimal(str(trade.size)),
            order_type=trade.order_type or "market",
            limit_price=limit_price or (Decimal(str(trade.price)) if trade.price is not None else None),
            strategy_id=str(trade.agent_id) if trade.agent_id else None,
            metadata=metadata or {"trade_id": str(trade.id)},
        )

        # Persistence compatibility
        intent.compat_trade = trade
        intent.compat_price = intent.limit_price
        intent.compat_size = intent.quantity
        intent.compat_id = uuid.uuid4()
        intent.compat_trade_id = trade.id

        # Use trade.outcome for backward compatibility only
        if hasattr(trade, "outcome") and trade.outcome:
            intent.compat_outcome = trade.outcome

        return intent
