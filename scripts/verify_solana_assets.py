import asyncio
import sys
import os
from decimal import Decimal

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.domain.assets import AssetId
from app.services.assets.asset_registry import AssetRegistry
from app.services.assets.bootstrap import bootstrap_asset_registry
from app.services.assets.asset_resolution_fingerprint import AssetResolutionFingerprint

async def verify_resolution():
    bootstrap_asset_registry()

    test_cases = [
        {"venue": "jupiter", "symbol": "SOL", "canonical_id": "SOL", "quote_asset": "USDC"},
        {"venue": "jupiter", "symbol": "USDC", "canonical_id": "USDC", "quote_asset": "USDC"},
        {"venue": "jupiter", "symbol": "UNKNOWN", "canonical_id": "UNKNOWN", "quote_asset": "USDC"},
        {"venue": "polymarket", "symbol": "ETH", "canonical_id": "0x123", "quote_asset": "USDC"},
    ]

    print("--- ASSET RESOLUTION VERIFICATION ---")

    for tc in test_cases:
        asset_id = AssetId(**tc)
        print(f"\nResolving: {asset_id.venue}:{asset_id.symbol}")

        # Resolve 10 times to verify determinism
        resolutions = []
        fingerprints = []

        for i in range(10):
            res = await AssetRegistry.resolve(asset_id)
            fp = AssetResolutionFingerprint.create(res)
            resolutions.append(res)
            fingerprints.append(fp)

        # Check if all fingerprints are same
        all_same = all(fp == fingerprints[0] for fp in fingerprints)

        res0 = resolutions[0]
        print(f"  Source: {res0.source}")
        print(f"  Decimals: {res0.asset.decimals}")
        print(f"  Confidence: {res0.confidence}")
        print(f"  External IDs: {res0.asset.metadata.external_identifiers}")
        print(f"  Fingerprint: {fingerprints[0]}")
        print(f"  Deterministic (10x): {'PASSED' if all_same else 'FAILED'}")

    # Verify lookup keys
    print("\n--- LOOKUP KEY VERIFICATION ---")
    sol_id = AssetId(venue="jupiter", symbol="SOL", canonical_id="So111...2", quote_asset="USDC")
    res_sol = await AssetRegistry.resolve(sol_id)
    print(f"Lookup by symbol 'SOL' -> mint: {res_sol.asset.metadata.external_identifiers.get('mint')}")

if __name__ == "__main__":
    asyncio.run(verify_resolution())
