from app.domain.execution.execution_intent import ExecutionIntent
from app.models.exchange_order import ExchangeOrder


class GenericTranslator:
    @staticmethod
    def to_exchange_order(intent: ExecutionIntent, trade_id, order_num=1, exchange="paper") -> ExchangeOrder:
        return ExchangeOrder(
            trade_id=trade_id,
            order_num=order_num,
            engine_type=exchange,
            exchange=exchange,
            side=intent.side,
            outcome=None,
            size=intent.quantity,
            price=intent.limit_price,
            slippage=str(intent.slippage_bps) if intent.slippage_bps else None,
            asset_id=intent.instrument.asset_identifier,
            idempotency_key=str(trade_id),
            status="pending",
        )
