import pytest
from app.domain.assets import AssetId
from app.services.assets.translators import JupiterAssetTranslator

@pytest.mark.asyncio
async def test_jupiter_translator_boundaries():
    translator = JupiterAssetTranslator()

    # Valid symbol
    aid_sol = AssetId(venue="jupiter", symbol="SOL", canonical_id="SOL", quote_asset="USDC")
    res_sol = await translator.resolve(aid_sol)
    assert "mint" in res_sol.asset.metadata.external_identifiers
    assert res_sol.confidence == 1.0

    # Unknown symbol
    aid_unk = AssetId(venue="jupiter", symbol="UNKNOWN", canonical_id="UNK", quote_asset="USDC")
    res_unk = await translator.resolve(aid_unk)
    assert "mint" not in res_unk.asset.metadata.external_identifiers
    assert res_unk.confidence == 0.5

from pydantic import ValidationError

def test_asset_id_immutability():
    aid = AssetId(venue="v", symbol="s", canonical_id="c", quote_asset="q")
    with pytest.raises(ValidationError):
        aid.venue = "new" # Frozen
