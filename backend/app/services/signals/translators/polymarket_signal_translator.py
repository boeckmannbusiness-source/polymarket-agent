from app.domain.signals import Signal, SignalAction
from app.strategies.signal import StructuredSignal


class PolymarketSignalTranslator:
    @staticmethod
    def to_structured(signal: Signal) -> StructuredSignal:
        action_to_signal = {
            SignalAction.BUY: "BUY_YES",
            SignalAction.SELL: "BUY_NO",
            SignalAction.HOLD: "NEUTRAL",
        }
        polymarket_signal = action_to_signal.get(signal.action, "NEUTRAL")
        instrument_meta = signal.instrument.metadata or {}

        return StructuredSignal(
            strategy=instrument_meta.get("strategy", "domain_signal"),
            signal=polymarket_signal,
            confidence=signal.confidence,
            market_id=instrument_meta.get("market_id") or signal.instrument.symbol,
            market_condition_id=instrument_meta.get("condition_id"),
            reason=instrument_meta.get("reason", "Signal from domain pipeline"),
            time_horizon=instrument_meta.get("time_horizon", "medium"),
            market_regime=instrument_meta.get("market_regime"),
            feature_values=signal.metadata,
        )

    @staticmethod
    def from_structured(structured: StructuredSignal) -> Signal:
        signal_to_action = {
            "BUY_YES": SignalAction.BUY,
            "BUY": SignalAction.BUY,
            "BUY_NO": SignalAction.SELL,
            "SELL": SignalAction.SELL,
            "NEUTRAL": SignalAction.HOLD,
            "HOLD": SignalAction.HOLD,
        }
        action = signal_to_action.get(structured.signal, SignalAction.HOLD)
        instrument_meta = {
            "strategy": structured.strategy,
            "market_id": structured.market_id,
            "condition_id": structured.market_condition_id,
            "reason": structured.reason,
            "time_horizon": structured.time_horizon,
            "market_regime": structured.market_regime,
            "risk_score": structured.risk_score,
        }
        from app.domain.execution.instrument import Instrument

        instrument = Instrument(
            venue="polymarket",
            symbol=structured.market_id or "",
            asset_identifier=str(structured.market_condition_id) if structured.market_condition_id else (structured.market_id or ""),
            quote_asset="USDC",
            metadata=instrument_meta,
        )
        return Signal(
            instrument=instrument,
            action=action,
            confidence=structured.confidence,
            metadata=structured.feature_values,
        )
