from app.domain.assets import AssetId, AssetResolution, Asset, AssetMetadata
from ..asset_resolver import AssetResolver

# Known mints for Jupiter
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

class JupiterAssetTranslator(AssetResolver):
    """READ ONLY. Resolve Solana assets using Jupiter metadata assumptions."""

    async def resolve(self, asset_id: AssetId) -> AssetResolution:
        # Map symbol to mint
        mint = self._resolve_mint(asset_id.symbol)

        metadata = AssetMetadata(
            external_identifiers={"mint": mint} if mint else {},
            venue_metadata={"venue": "jupiter"}
        )

        decimals = 9 if asset_id.symbol.upper() == "SOL" else 6

        return AssetResolution(
            asset=Asset(
                asset_id=asset_id,
                decimals=decimals,
                metadata=metadata
            ),
            source="jupiter_translator",
            confidence=1.0 if mint else 0.5
        )

    def _resolve_mint(self, symbol: str) -> str | None:
        lookup = {
            "SOL": SOL_MINT,
            "USDC": USDC_MINT,
        }
        return lookup.get(symbol.upper())
