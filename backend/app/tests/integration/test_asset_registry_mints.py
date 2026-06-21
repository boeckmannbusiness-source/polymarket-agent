import pytest
from app.services.assets import AssetRegistry
from app.services.assets.bootstrap import bootstrap_asset_registry
from app.domain.assets import AssetId
from app.services.assets.asset_resolution_fingerprint import AssetResolutionFingerprint

@pytest.mark.asyncio
async def test_sol_mint_resolution():
    bootstrap_asset_registry()
    sol_mint = "So11111111111111111111111111111111111111112"
    asset_id = AssetId(
        venue="jupiter",
        symbol="SOL",
        canonical_id=sol_mint,
        quote_asset="USDC"
    )
    resolution = await AssetRegistry.resolve(asset_id)
    assert resolution.asset.asset_id.symbol == "SOL"
    assert resolution.asset.metadata.external_identifiers.get("mint") == sol_mint
    assert resolution.asset.decimals == 9
    assert resolution.confidence == 1.0

@pytest.mark.asyncio
async def test_asset_resolution_determinism():
    bootstrap_asset_registry()
    asset_id = AssetId(
        venue="jupiter",
        symbol="SOL",
        canonical_id="So11111111111111111111111111111111111111112",
        quote_asset="USDC"
    )
    fingerprints = []
    for _ in range(10):
        resolution = await AssetRegistry.resolve(asset_id)
        fp = AssetResolutionFingerprint.create(resolution)
        fingerprints.append(fp)
    assert len(set(fingerprints)) == 1
    print(f"\nDeterministic Fingerprint: {fingerprints[0]}")
