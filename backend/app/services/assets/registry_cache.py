import time
from typing import Any
from app.domain.assets import AssetId, AssetResolution


class RegistryCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: dict[AssetId, tuple[AssetResolution, float]] = {}
        self._ttl = ttl_seconds

    def get(self, asset_id: AssetId) -> AssetResolution | None:
        if asset_id not in self._cache:
            return None

        res, ts = self._cache[asset_id]
        if time.time() - ts > self._ttl:
            del self._cache[asset_id]
            return None

        return res

    def set(self, asset_id: AssetId, resolution: AssetResolution) -> None:
        self._cache[asset_id] = (resolution, time.time())

    def invalidate(self, asset_id: AssetId) -> None:
        if asset_id in self._cache:
            del self._cache[asset_id]

    def clear(self) -> None:
        self._cache.clear()
