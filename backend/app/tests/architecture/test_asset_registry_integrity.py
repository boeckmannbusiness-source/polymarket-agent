import pytest
import asyncio
from app.domain.assets import AssetId, Asset, AssetMetadata, AssetResolution
from app.services.assets import AssetRegistry, RegistryCache
from app.services.assets.translators import JupiterAssetTranslator, PolymarketAssetTranslator

@pytest.mark.asyncio
async def test_asset_registry_resolution():
    AssetRegistry.register_resolver("jupiter", JupiterAssetTranslator())
    AssetRegistry.register_resolver("polymarket", PolymarketAssetTranslator())

    # Test Jupiter resolution
    aid_sol = AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC")
    res_sol = await AssetRegistry.resolve(aid_sol)

    assert res_sol.asset.decimals == 9
    assert res_sol.asset.metadata.external_identifiers["mint"] == "So11111111111111111111111111111111111111112"

    # Test Polymarket resolution
    aid_pm = AssetId(venue="polymarket", symbol="TRUMP-WIN", canonical_id="0x123", quote_asset="USDC")
    res_pm = await AssetRegistry.resolve(aid_pm)

    assert res_pm.asset.decimals == 6
    assert res_pm.asset.metadata.external_identifiers["condition_id"] == "0x123"

def test_registry_cache_determinism():
    cache = RegistryCache(ttl_seconds=10)
    aid = AssetId(venue="test", symbol="T", canonical_id="C", quote_asset="Q")

    asset = Asset(asset_id=aid, decimals=18, metadata=AssetMetadata())
    res = AssetResolution(asset=asset, source="test", confidence=1.0)

    cache.set(aid, res)
    assert cache.get(aid) == res

    cache.invalidate(aid)
    assert cache.get(aid) is None

@pytest.mark.asyncio
async def test_resolve_many_integrity():
    AssetRegistry.register_resolver("jupiter", JupiterAssetTranslator())

    aids = [
        AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC"),
        AssetId(venue="jupiter", symbol="USDC", canonical_id="USDC", quote_asset="USDC")
    ]

    results = await AssetRegistry.resolve_many(aids)
    assert len(results) == 2
    assert results[0].asset.asset_id.symbol == "SOL"
    assert results[1].asset.asset_id.symbol == "USDC"
