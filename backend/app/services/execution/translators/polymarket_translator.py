from app.domain.execution.execution_intent import ExecutionIntent
from app.models.exchange_order import ExchangeOrder


class PolymarketTranslator:
    @staticmethod
    def to_exchange_order(intent: ExecutionIntent, trade_id, order_num=1) -> ExchangeOrder:
        outcome = intent.metadata.get("outcome") if intent.metadata else None
        clob_asset_id = intent.instrument.metadata.get("clob_asset_id") if intent.instrument.metadata else None
        condition_id = intent.instrument.metadata.get("condition_id") if intent.instrument.metadata else None

        return ExchangeOrder(
            trade_id=trade_id,
            order_num=order_num,
            engine_type="live",
            exchange="live_polymarket",
            side=intent.side,
            outcome=outcome,
            size=intent.quantity,
            price=intent.limit_price,
            slippage=str(intent.slippage_bps) if intent.slippage_bps else None,
            asset_id=intent.instrument.asset_identifier,
            clob_asset_id=clob_asset_id,
            idempotency_key=str(trade_id),
            status="pending",
        )
