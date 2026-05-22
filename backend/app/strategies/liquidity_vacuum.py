from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class LiquidityVacuumStrategy(BaseStrategy):
    name = "liquidity_vacuum"
    version = "1.0.0"
    description = "Detects markets where liquidity is being rapidly consumed, suggesting impending price moves"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
