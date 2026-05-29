import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass
class TradeRecord:
    timestamp: datetime
    price: float
    size: float
    side: str
    maker: str | None = None
    taker: str | None = None


@dataclass
class MarketContext:
    condition_id: str
    market_id: str | None = None
    outcomes: list[str] | None = None

    current_price: float | None = None
    current_mid: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    outcome_prices: dict[str, float] = field(default_factory=dict)

    volume_window_5m: float = 0.0
    volume_window_15m: float = 0.0
    volume_window_1h: float = 0.0
    volume_window_4h: float = 0.0
    volume_window_24h: float = 0.0

    trade_count_5m: int = 0
    trade_count_15m: int = 0
    trade_count_1h: int = 0
    trade_count_4h: int = 0
    trade_count_24h: int = 0

    price_history: list[tuple[datetime, float]] = field(default_factory=list)
    volume_history: list[tuple[datetime, float]] = field(default_factory=list)

    bid_depth: float = 0.0
    ask_depth: float = 0.0
    orderbook_imbalance: float = 0.0

    end_date: datetime | None = None
    created_at: datetime | None = None
    slug: str | None = None

    whale_buy_volume_1h: float = 0.0
    whale_sell_volume_1h: float = 0.0
    whale_pressure: float = 0.0

    _ema_volatility: float | None = field(init=False, default=None)
    _ema_alpha: float = field(init=False, default=0.3)
    _regime_persistence_count: int = field(init=False, default=3)
    _current_regime: str = field(init=False, default="normal")
    _regime_confirmations: int = field(init=False, default=0)

    last_event_timestamp: datetime | None = None

    def update_trade(self, timestamp: datetime, price: float, size: float, side: str,
                     maker: str | None = None, taker: str | None = None):
        trade = TradeRecord(timestamp, price, size, side, maker, taker)
        self.last_event_timestamp = timestamp

        self.current_price = price
        self.current_mid = price
        self.outcome_prices[side] = price
        self.price_history.append((timestamp, price))
        self.volume_history.append((timestamp, size))

        self._prune_windows(timestamp)

        if side in ("buy", "BUY"):
            self.volume_window_5m += size
            self.volume_window_15m += size
            self.volume_window_1h += size
            self.volume_window_4h += size
            self.volume_window_24h += size
            self.trade_count_5m += 1
            self.trade_count_15m += 1
            self.trade_count_1h += 1
            self.trade_count_4h += 1
            self.trade_count_24h += 1
            if size >= 500:
                self.whale_buy_volume_1h += size
        else:
            self.volume_window_5m += size
            self.volume_window_15m += size
            self.volume_window_1h += size
            self.volume_window_4h += size
            self.volume_window_24h += size
            self.trade_count_5m += 1
            self.trade_count_15m += 1
            self.trade_count_1h += 1
            self.trade_count_4h += 1
            self.trade_count_24h += 1
            if size >= 500:
                self.whale_sell_volume_1h += size

        total_whale = self.whale_buy_volume_1h + self.whale_sell_volume_1h
        if total_whale > 0:
            self.whale_pressure = (self.whale_buy_volume_1h - self.whale_sell_volume_1h) / total_whale

    def _prune_windows(self, now: datetime):
        cutoff_5m = now.timestamp() - 300
        cutoff_15m = now.timestamp() - 900
        cutoff_1h = now.timestamp() - 3600
        cutoff_4h = now.timestamp() - 14400
        cutoff_24h = now.timestamp() - 86400

        def prune(history, age_cutoff):
            while history and history[0][0].timestamp() < age_cutoff:
                history.pop(0)

        prune(self.price_history, cutoff_1h)

        i = 0
        while i < len(self.volume_history):
            ts = self.volume_history[i][0].timestamp()
            vol = self.volume_history[i][1]
            if ts < cutoff_5m:
                self.volume_window_5m = max(0.0, self.volume_window_5m - vol)
                self.trade_count_5m = max(0, self.trade_count_5m - 1)
            if ts < cutoff_15m:
                self.volume_window_15m = max(0.0, self.volume_window_15m - vol)
                self.trade_count_15m = max(0, self.trade_count_15m - 1)
            if ts < cutoff_1h:
                self.volume_window_1h = max(0.0, self.volume_window_1h - vol)
                self.trade_count_1h = max(0, self.trade_count_1h - 1)
            if ts < cutoff_4h:
                self.volume_window_4h = max(0.0, self.volume_window_4h - vol)
                self.trade_count_4h = max(0, self.trade_count_4h - 1)
            if ts < cutoff_24h:
                self.volume_window_24h = max(0.0, self.volume_window_24h - vol)
                self.trade_count_24h = max(0, self.trade_count_24h - 1)
            i += 1

        while self.volume_history and self.volume_history[0][0].timestamp() < cutoff_5m:
            self.volume_history.pop(0)

    def get_volatility(self, window_seconds: int = 3600) -> float | None:
        if len(self.price_history) < 2:
            return None
        cutoff = self.last_event_timestamp.timestamp() - window_seconds if self.last_event_timestamp else 0
        prices = [p for ts, p in self.price_history if ts.timestamp() >= cutoff]
        if len(prices) < 2:
            return None
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        return variance ** 0.5

    def _has_sufficient_window_coverage(self, window_seconds: int) -> bool:
        if not self.last_event_timestamp or len(self.price_history) < 2:
            return False
        cutoff_ts = self.last_event_timestamp.timestamp() - window_seconds
        closest_ts, closest_diff = None, float("inf")
        for ts, _ in self.price_history:
            diff = abs(ts.timestamp() - cutoff_ts)
            if diff < closest_diff:
                closest_diff = diff
                closest_ts = ts.timestamp()
        if closest_ts is None:
            return False
        return closest_diff <= window_seconds * 0.5

    def get_momentum(self, window_seconds: int = 3600) -> float | None:
        if not self.current_price or len(self.price_history) < 2 or not self.last_event_timestamp:
            return None
        if not self._has_sufficient_window_coverage(window_seconds):
            return None
        cutoff_ts = self.last_event_timestamp.timestamp() - window_seconds
        best, best_diff = None, float("inf")
        for ts, p in self.price_history:
            diff = abs(ts.timestamp() - cutoff_ts)
            if diff < best_diff:
                best_diff = diff
                best = p
        if best is None:
            return None
        return (self.current_price - best) / best

    def get_outcome_price(self, signal_direction: str) -> float | None:
        """Get the relevant outcome price for a signal direction (BUY_YES/BUY_NO).
        Maps BUY_YES -> first outcome, BUY_NO -> second outcome."""
        if not self.outcome_prices:
            return self.current_price
        if signal_direction == "BUY_YES":
            if self.outcomes and len(self.outcomes) > 0:
                return self.outcome_prices.get(self.outcomes[0])
            return self.outcome_prices.get("Yes") or self.outcome_prices.get("yes") or self.current_price
        elif signal_direction == "BUY_NO":
            if self.outcomes and len(self.outcomes) > 1:
                return self.outcome_prices.get(self.outcomes[1])
            return self.outcome_prices.get("No") or self.outcome_prices.get("no") or self.current_price
        return self.current_price

    def _compute_raw_regime(self) -> str:
        vol = self.get_volatility(3600)
        mom = self.get_momentum(3600)
        if self.current_price is None or self.current_mid is None:
            return "unknown"
        spread_ratio = (self.spread / self.current_mid) if self.current_mid and self.spread else 0
        if spread_ratio and spread_ratio > 0.05:
            return "illiquid"
        if vol and vol > 0.1 * (self.current_mid or 0.5):
            return "high_volatility"
        if vol and vol < 0.01 * (self.current_mid or 0.5):
            return "low_volatility"
        if mom and abs(mom) > 0.05:
            return "momentum"
        if mom and abs(mom) < 0.005:
            return "mean_reverting"
        return "normal"

    def get_regime(self) -> str:
        if self._ema_volatility is None:
            raw_vol = self.get_volatility(3600)
            self._ema_volatility = raw_vol if raw_vol is not None else 0.0
        else:
            raw_vol = self.get_volatility(3600)
            if raw_vol is not None:
                self._ema_volatility = (
                    self._ema_alpha * raw_vol + (1.0 - self._ema_alpha) * self._ema_volatility
                )
        raw_regime = self._compute_raw_regime()
        if raw_regime == self._current_regime:
            self._regime_confirmations = min(self._regime_confirmations + 1, self._regime_persistence_count)
        else:
            self._regime_confirmations -= 1
            if self._regime_confirmations <= 0:
                self._current_regime = raw_regime
                self._regime_confirmations = 0
        return self._current_regime

    @staticmethod
    def classify_archetype(slug: str | None, title: str | None) -> str:
        text = (slug or "") + " " + (title or "")
        text_lower = text.lower()
        sports_keywords = ["nba", "mlb", "nfl", "nhl", "wta", "atp", "itf", "mls", "ufc",
                           "esports", "handicap", "spread", "over/under", "match", "set",
                           "game", "furia", "fnc", "bbl", "cavaliers", "knicks", "padres",
                           "twins", "white sox", "sakellaridis", "overbeck", "udvardy",
                           "golubic", "ostapenko", "seidel", "dc united", "mls cup",
                           "soccer", "basketball", "tennis", "baseball", "football"]
        crypto_keywords = ["btc", "bitcoin", "eth", "ethereum", "sol", "solana", "crypto",
                           "token", "hood", "robinhood", "price", "$"]
        politics_keywords = ["trump", "election", "ballot", "president", "political",
                             "castex", "french", "diplomatic", "russia", "ukraine",
                             "senate", "congress", "vote", "nomination"]
        macro_keywords = ["fed", "rates", "interest rate", "gdp", "inflation", "regulation",
                          "recession", "central bank", "cpi", "unemployment", "tariff"]
        weather_keywords = ["temperature", "weather", "celsius", "fahrenheit", "miami",
                            "amsterdam", "seoul", "high temperature"]

        for kw in sports_keywords:
            if kw in text_lower:
                return "sports"
        for kw in crypto_keywords:
            if kw in text_lower:
                return "crypto"
        for kw in politics_keywords:
            if kw in text_lower:
                return "politics"
        for kw in weather_keywords:
            if kw in text_lower:
                return "weather"
        for kw in macro_keywords:
            if kw in text_lower:
                return "macro"
        return "generic"

    def to_feature_dict(self) -> dict:
        p = self.current_price
        price_zone = None
        distance_to_05 = None
        distance_to_extremes = None
        entropy = None
        proximity_to_resolution = None
        market_maturity = None
        resolution_bucket = None
        hours_to_resolution = None
        if p is not None:
            distance_to_05 = abs(p - 0.5)
            distance_to_extremes = min(p, 1.0 - p) if 0 <= p <= 1 else None
            if 0 < p < 1:
                entropy = -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))
            else:
                entropy = 0.0
            if p <= 0.2:
                price_zone = "crisis"
            elif p <= 0.4:
                price_zone = "discount"
            elif p <= 0.6:
                price_zone = "fair"
            elif p <= 0.8:
                price_zone = "premium"
            else:
                price_zone = "extreme"

        now = datetime.now(timezone.utc)
        if self.end_date is not None:
            remaining_sec = (self.end_date - now).total_seconds()
            proximity_to_resolution = max(0.0, remaining_sec / 86400.0)
            hours_to_resolution = max(0.0, remaining_sec / 3600.0)
            if remaining_sec <= 3600:
                resolution_bucket = "last_hour"
            elif remaining_sec <= 86400:
                resolution_bucket = "last_day"
            elif remaining_sec <= 604800:
                resolution_bucket = "last_week"
            else:
                resolution_bucket = "distant"

        if self.created_at is not None and self.end_date is not None and self.end_date > self.created_at:
            total = (self.end_date - self.created_at).total_seconds()
            elapsed = (now - self.created_at).total_seconds()
            market_maturity = min(1.0, max(0.0, elapsed / total))

        archetype = self.classify_archetype(self.slug, None)

        return {
            "condition_id": self.condition_id,
            "market_id": self.market_id,
            "current_price": p,
            "current_mid": self.current_mid,
            "spread": self.spread,
            "volume_5m": self.volume_window_5m,
            "volume_15m": self.volume_window_15m,
            "volume_1h": self.volume_window_1h,
            "volume_4h": self.volume_window_4h,
            "volume_24h": self.volume_window_24h,
            "trade_count_5m": self.trade_count_5m,
            "trade_count_15m": self.trade_count_15m,
            "trade_count_1h": self.trade_count_1h,
            "trade_count_4h": self.trade_count_4h,
            "trade_count_24h": self.trade_count_24h,
            "volatility_1h": self.get_volatility(3600),
            "momentum_1h": self.get_momentum(3600),
            "orderbook_imbalance": self.orderbook_imbalance,
            "whale_pressure": self.whale_pressure,
            "whale_buy_volume_1h": self.whale_buy_volume_1h,
            "whale_sell_volume_1h": self.whale_sell_volume_1h,
            "regime": self.get_regime(),
            "price_zone": price_zone,
            "distance_to_0.5": distance_to_05,
            "distance_to_extremes": distance_to_extremes,
            "entropy": entropy,
            "proximity_to_resolution_days": proximity_to_resolution,
            "hours_to_resolution": hours_to_resolution,
            "resolution_bucket": resolution_bucket,
            "market_maturity": market_maturity,
            "archetype": archetype,
        }
