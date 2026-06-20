from app.domain.assets import AssetId, AssetResolution, Asset, AssetMetadata
from ..asset_resolver import AssetResolver


class PolymarketAssetTranslator(AssetResolver):
    """Compatibility only. Resolve Polymarket assets (condition IDs)."""

    async def resolve(self, asset_id: AssetId) -> AssetResolution:
        # Compatibility layer: if it looks like a condition ID, we can enrich it
        # In actual implementation this might query a database or external API
        metadata = AssetMetadata(
            external_identifiers={"condition_id": asset_id.canonical_id},
            venue_metadata={"venue": "polymarket"}
        )

        return AssetResolution(
            asset=Asset(
                asset_id=asset_id,
                decimals=6, # Polymarket USDC is 6 decimals
                metadata=metadata
            ),
            source="polymarket_translator",
            confidence=1.0
        )
