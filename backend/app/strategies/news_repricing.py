from app.strategies.base import BaseStrategy, StrategyConfig
from app.strategies.signal import StructuredSignal


class NewsRepricingStrategy(BaseStrategy):
    name = "news_repricing"
    version = "1.0.0"
    description = "Detects price movements correlated with external news events or social sentiment"

    async def generate_signal(self, market_state: dict) -> StructuredSignal | None:
        return None
