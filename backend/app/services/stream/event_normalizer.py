from datetime import datetime, timezone
from typing import Any

from app.models import Fill, ExchangeOrder, Trade


class EventNormalizer:
    @staticmethod
    def normalize_fill_event(fill: Fill) -> dict[str, Any]:
        return {
            "type": "fill.created",
            "timestamp": fill.filled_at.isoformat() if fill.filled_at else datetime.now(timezone.utc).isoformat(),
            "entity_type": "fill",
            "entity_id": str(fill.id),
            "channel": "fills",
            "payload": {
                "fill_id": str(fill.id),
                "exchange_order_id": str(fill.exchange_order_id),
                "trade_id": str(fill.trade_id),
                "market_id": str(fill.market_id),
                "side": fill.side,
                "outcome": fill.outcome,
                "size": float(fill.size),
                "price": float(fill.price),
                "fee": float(fill.fee),
                "filled_at": fill.filled_at.isoformat() if fill.filled_at else None,
            },
        }

    @staticmethod
    def normalize_order_event(order: ExchangeOrder, event_type: str = "order.updated") -> dict[str, Any]:
        return {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "order",
            "entity_id": str(order.id),
            "channel": "orders",
            "payload": {
                "order_id": str(order.id),
                "trade_id": str(order.trade_id),
                "engine_type": order.engine_type,
                "status": order.status,
                "side": order.side,
                "outcome": order.outcome,
                "size": float(order.size),
                "filled_size": float(order.filled_size) if order.filled_size else 0.0,
                "price": float(order.price) if order.price else None,
                "filled_price": float(order.filled_price) if order.filled_price else None,
                "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            },
        }

    @staticmethod
    def normalize_trade_event(trade: Trade, event_type: str = "trade.updated") -> dict[str, Any]:
        return {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "trade",
            "entity_id": str(trade.id),
            "channel": "trades",
            "payload": {
                "trade_id": str(trade.id),
                "market_id": str(trade.market_id) if trade.market_id else None,
                "side": trade.side,
                "outcome": trade.outcome,
                "status": trade.status,
                "size": float(trade.size),
                "agent_id": trade.agent_id,
                "created_at": trade.created_at.isoformat() if trade.created_at else None,
            },
        }

    @staticmethod
    def normalize_portfolio_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "portfolio.snapshot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "portfolio",
            "entity_id": "overview",
            "channel": "portfolio",
            "payload": snapshot,
        }

    @staticmethod
    def normalize_pnl_update(pnl_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "pnl.updated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "portfolio",
            "entity_id": "pnl",
            "channel": "portfolio",
            "payload": pnl_data,
        }

    @staticmethod
    def normalize_drift_event(drift_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "drift.detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "risk",
            "entity_id": drift_data.get("order_id", "unknown"),
            "channel": "monitoring",
            "payload": drift_data,
        }

    @staticmethod
    def normalize_execution_error(error_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "execution.error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entity_type": "execution",
            "entity_id": error_data.get("order_id", "unknown"),
            "channel": "monitoring",
            "payload": error_data,
        }
