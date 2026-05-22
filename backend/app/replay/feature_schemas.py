from datetime import datetime

FEATURE_SCHEMA_V1 = {
    "version": "1.0.0",
    "description": "Initial feature schema — market state features from MarketContext",
    "features": [
        {"name": "condition_id", "type": "string", "description": "Polymarket condition ID"},
        {"name": "market_id", "type": "string", "description": "Internal market UUID"},
        {"name": "current_price", "type": "float", "description": "Last trade price"},
        {"name": "current_mid", "type": "float", "description": "Mid price"},
        {"name": "spread", "type": "float", "description": "Current spread"},
        {"name": "volume_5m", "type": "float", "description": "Trade volume last 5 minutes"},
        {"name": "volume_15m", "type": "float", "description": "Trade volume last 15 minutes"},
        {"name": "volume_1h", "type": "float", "description": "Trade volume last 1 hour"},
        {"name": "volume_4h", "type": "float", "description": "Trade volume last 4 hours"},
        {"name": "volume_24h", "type": "float", "description": "Trade volume last 24 hours"},
        {"name": "trade_count_5m", "type": "int", "description": "Trade count last 5 minutes"},
        {"name": "trade_count_15m", "type": "int", "description": "Trade count last 15 minutes"},
        {"name": "trade_count_1h", "type": "int", "description": "Trade count last 1 hour"},
        {"name": "trade_count_4h", "type": "int", "description": "Trade count last 4 hours"},
        {"name": "trade_count_24h", "type": "int", "description": "Trade count last 24 hours"},
        {"name": "volatility_1h", "type": "float", "description": "Price volatility (std) last 1 hour"},
        {"name": "momentum_1h", "type": "float", "description": "Price momentum last 1 hour"},
        {"name": "orderbook_imbalance", "type": "float", "description": "Orderbook bid/ask imbalance"},
        {"name": "whale_pressure", "type": "float", "description": "Net whale buying pressure (-1 to 1)"},
        {"name": "whale_buy_volume_1h", "type": "float", "description": "Whale buy volume last 1 hour"},
        {"name": "whale_sell_volume_1h", "type": "float", "description": "Whale sell volume last 1 hour"},
        {"name": "regime", "type": "string", "description": "Market regime classification"},
    ],
    "rules": {
        "current_price": {"required": False, "nullable": True},
        "volume_1h": {"min": 0},
        "trade_count_1h": {"min": 0},
        "whale_pressure": {"min": -1.0, "max": 1.0},
    },
}


FEATURE_SCHEMAS = {
    "1.0.0": FEATURE_SCHEMA_V1,
}


def get_feature_schema(version: str = "1.0.0") -> dict:
    schema = FEATURE_SCHEMAS.get(version)
    if schema is None:
        raise ValueError(f"Unknown feature schema version: {version}. Available: {list(FEATURE_SCHEMAS.keys())}")
    return schema


def list_feature_versions() -> list[str]:
    return sorted(FEATURE_SCHEMAS.keys())


def validate_features(features: dict, version: str = "1.0.0") -> list[str]:
    schema = get_feature_schema(version)
    errors = []
    for feat_def in schema["features"]:
        name = feat_def["name"]
        ftype = feat_def["type"]
        rules = schema.get("rules", {}).get(name, {})
        required = rules.get("required", True)
        nullable = rules.get("nullable", False)
        value = features.get(name)

        if required and value is None and not nullable:
            errors.append(f"Missing required feature: {name}")
        if value is not None:
            if ftype == "float" and not isinstance(value, (int, float)):
                errors.append(f"Feature {name}: expected float, got {type(value).__name__}")
            if ftype == "int" and not isinstance(value, int):
                errors.append(f"Feature {name}: expected int, got {type(value).__name__}")
            min_val = rules.get("min")
            max_val = rules.get("max")
            if min_val is not None and isinstance(value, (int, float)) and value < min_val:
                errors.append(f"Feature {name}: {value} < min {min_val}")
            if max_val is not None and isinstance(value, (int, float)) and value > max_val:
                errors.append(f"Feature {name}: {value} > max {max_val}")
    return errors
