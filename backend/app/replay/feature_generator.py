from app.replay.market_state import MarketContext


class FeatureGenerator:
    @staticmethod
    def generate(context: MarketContext) -> dict:
        return context.to_feature_dict()
