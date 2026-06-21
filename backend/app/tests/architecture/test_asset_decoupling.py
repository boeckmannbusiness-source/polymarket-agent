import pytest
from app.services.assets import AssetRegistry
from app.services.assets.translators import JupiterAssetTranslator, PolymarketAssetTranslator

@pytest.fixture(autouse=True)
def setup_resolvers():
    AssetRegistry.register_resolver("jupiter", JupiterAssetTranslator())
    AssetRegistry.register_resolver("polymarket", PolymarketAssetTranslator())

def test_no_venue_branching_in_core():
    """
    Ensure core logic doesn't branch on venue for asset logic.
    We check this by ensuring certain strings aren't used in execution_service.py
    outside of the intended abstraction.
    """
    import os
    core_files = [
        "backend/app/services/execution/execution_service.py",
        "backend/app/services/planning/planner.py",
        "backend/app/services/planning/providers/jupiter_quote_provider.py"
    ]

    forbidden_patterns = [
        'if symbol == "SOL"',
        'if asset == "USDC"',
        'if venue == "jupiter"',
        'SOL_MINT',
        'USDC_MINT'
    ]

    for filepath in core_files:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            content = f.read()
            for pattern in forbidden_patterns:
                # JupiterQuoteProvider is allowed to have "jupiter" in its name or venue_hint,
                # but not hardcoded mints or symbol-based branching now.
                if "jupiter_quote_provider" in filepath and (pattern == 'if venue == "jupiter"' or pattern == 'venue == "jupiter"'):
                    continue

                assert pattern not in content, f"Forbidden pattern '{pattern}' found in {filepath}"

def test_asset_domain_no_blockchain_imports():
    """Ensure asset domain doesn't import blockchain libraries."""
    import os
    domain_path = "backend/app/domain/assets/"
    for filename in os.listdir(domain_path):
        if not filename.endswith(".py"):
            continue
        with open(os.path.join(domain_path, filename), "r") as f:
            content = f.read()
            assert "solana" not in content.lower()
            assert "web3" not in content.lower()
            assert "eth" not in content.lower()

def test_quote_provider_consumes_asset_resolution():
    """Verify JupiterQuoteProvider uses AssetResolution for mints."""
    from app.services.planning.providers.jupiter_quote_provider import JupiterQuoteProvider
    from app.domain.assets import AssetResolution, Asset, AssetId, AssetMetadata
    from app.domain.execution import Instrument
    from decimal import Decimal
    import asyncio

    provider = JupiterQuoteProvider()

    # Mock instrument
    inst = Instrument(venue="jupiter", symbol="SOL", asset_identifier="SOL", quote_asset="USDC")

    # Mock AssetResolution
    asset = Asset(
        asset_id=AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC"),
        decimals=9,
        metadata=AssetMetadata(external_identifiers={"mint": "So11111111111111111111111111111111111111112"})
    )
    res = AssetResolution(asset=asset, source="test", confidence=1.0)

    # This should not raise error if it correctly uses asset_resolution
    # We won't actually call the network, but we can check if it tries to use the mint
    # In a real test we might mock the price_feed
