import pytest
from app.domain.assets import AssetId, AssetResolution, Asset, AssetMetadata
from app.services.assets import AssetRegistry
from app.services.assets.asset_resolution_fingerprint import AssetResolutionFingerprint
from app.services.assets.translators import JupiterAssetTranslator

@pytest.mark.asyncio
async def test_asset_resolution_determinism_consistency():
    """Verify that 10 identical runs produce identical fingerprints."""
    translator = JupiterAssetTranslator()
    aid = AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC")

    fingerprints = []
    for _ in range(10):
        res = await translator.resolve(aid)
        fp = AssetResolutionFingerprint.create(res)
        fingerprints.append(fp)

    # Check all are identical
    assert len(set(fingerprints)) == 1, "Fingerprints not stable across identical runs"
    assert res.is_deterministic() == True

@pytest.mark.asyncio
async def test_fingerprint_ignores_non_asset_state():
    """Verify fingerprint doesn't change with irrelevant resolution metadata."""
    aid = AssetId(venue="test", symbol="T", canonical_id="C", quote_asset="Q")
    asset = Asset(asset_id=aid, decimals=18, metadata=AssetMetadata())

    res1 = AssetResolution(asset=asset, source="test", confidence=1.0, resolution_metadata={"time": 100})
    res2 = AssetResolution(asset=asset, source="test", confidence=1.0, resolution_metadata={"time": 200})

    fp1 = AssetResolutionFingerprint.create(res1)
    fp2 = AssetResolutionFingerprint.create(res2)

    assert fp1 == fp2, "Fingerprint should only depend on immutable asset state"
