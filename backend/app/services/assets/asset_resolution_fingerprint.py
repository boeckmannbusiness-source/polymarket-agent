import hashlib
import json
from app.domain.assets import AssetResolution


class AssetResolutionFingerprint:
    @staticmethod
    def create(resolution: AssetResolution) -> str:
        """Create a deterministic fingerprint of an asset resolution.

        Depends only on immutable fields:
        - asset_id (venue, symbol, canonical_id, quote_asset)
        - decimals
        - metadata (external_identifiers, venue_metadata)
        - source
        - confidence
        """
        # Extract components in a stable way
        data = {
            "asset_id": resolution.asset.asset_id.model_dump(),
            "decimals": resolution.asset.decimals,
            "metadata": resolution.asset.metadata.model_dump(),
            "source": resolution.source,
            "confidence": resolution.confidence,
        }

        # Serialize to stable JSON
        serialized = json.dumps(data, sort_keys=True)

        # Create hash
        return hashlib.sha256(serialized.encode()).hexdigest()
