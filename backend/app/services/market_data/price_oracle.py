import time


class PriceOracle:
    """In-memory price cache with TTL.

    Stores latest observed price per (symbol, venue) pair.
    """

    def __init__(self, ttl_seconds: float = 60.0):
        self._ttl = ttl_seconds
        self._prices: dict[tuple[str, str], tuple[float, float]] = {}

    def get_price(self, symbol: str, venue: str) -> float | None:
        key = (symbol, venue)
        entry = self._prices.get(key)
        if entry is None:
            return None
        price, ts = entry
        if time.time() - ts > self._ttl:
            del self._prices[key]
            return None
        return price

    def set_price(self, symbol: str, venue: str, price: float) -> None:
        key = (symbol, venue)
        self._prices[key] = (price, time.time())

    def get_all_prices(self) -> dict[tuple[str, str], float]:
        now = time.time()
        result = {}
        for key, (price, ts) in list(self._prices.items()):
            if now - ts <= self._ttl:
                result[key] = price
            else:
                del self._prices[key]
        return result

    def clear(self) -> None:
        self._prices.clear()
