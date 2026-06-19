from app.domain.markets import InstrumentId, Market, MarketResolution
from app.domain.execution import Instrument as ExecutionInstrument


class PolymarketMarketTranslator:
    @staticmethod
    def instrument_to_market(instrument: InstrumentId, condition_id: str | None = None,
                             clob_asset_id: str | None = None) -> Market:
        metadata = {}
        if condition_id:
            metadata["condition_id"] = condition_id
        if clob_asset_id:
            metadata["clob_asset_id"] = clob_asset_id
        return Market(
            instrument_id=instrument,
            metadata=metadata or None,
            execution_constraints={
                "venue": "polymarket",
                "order_types": ["market", "limit"],
                "requires_outcome": True,
            },
        )

    @staticmethod
    def market_to_execution_instrument(market: Market) -> ExecutionInstrument:
        meta = market.metadata or {}
        return ExecutionInstrument(
            venue="live_polymarket",
            symbol=market.instrument_id.symbol,
            asset_identifier=meta.get("clob_asset_id") or market.instrument_id.symbol,
            quote_asset=market.instrument_id.quote_asset,
            metadata=meta,
        )

    @staticmethod
    def execution_to_instrument_id(exec_instrument: ExecutionInstrument) -> InstrumentId:
        return InstrumentId(
            venue="polymarket",
            symbol=exec_instrument.symbol,
            quote_asset=exec_instrument.quote_asset,
        )
