from pydantic import BaseModel
from .asset import Asset


class AssetResolution(BaseModel):
    asset: Asset
    source: str
    confidence: float
    resolution_metadata: dict = {}

    def is_deterministic(self) -> bool:
        """Check if resolution is based on deterministic metadata."""
        # Resolutions from translators with full confidence are typically deterministic
        return self.confidence >= 1.0 and self.source != "fallback"
