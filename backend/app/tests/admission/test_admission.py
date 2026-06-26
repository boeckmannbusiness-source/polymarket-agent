import pytest
from decimal import Decimal
from app.domain.assets.asset_id import AssetId
from app.domain.admission.models import (
    AssetSnapshot,
    AdmissionDecision,
    MarketQualityDecision,
    AdmissionReceipt
)
from app.domain.capabilities.capability_snapshot import CapabilitySnapshot
from app.services.admission.admission_service import AdmissionService
from app.services.admission.market_quality_engine import MarketQualityEngine
from app.services.admission.policy import AssetAdmissionPolicy
from app.domain.admission.fingerprint import AdmissionFingerprint

@pytest.fixture
def admission_service():
    return AdmissionService()

@pytest.fixture
def asset_id():
    return AssetId(venue="jupiter", symbol="TEST", canonical_id="test_id", quote_asset="USDC")

@pytest.fixture
def capability_snapshot():
    return CapabilitySnapshot(
        execution_mode="SIMULATION",
        rpc_permissions=["READ"],
        simulation_enabled=True,
        signing_enabled=False,
        broadcast_enabled=False
    )

def create_snapshot(asset_id, market_cap=Decimal("2000000"), liquidity=Decimal("100000"), age=10, concentration=None, route=True):
    holder_dist = {}
    if concentration:
        holder_dist["top"] = concentration

    route_snapshot = {"confidence": "0.9"} if route else {}

    return AssetSnapshot(
        asset_id=asset_id,
        symbol=asset_id.symbol,
        venue=asset_id.venue,
        market_cap=market_cap,
        liquidity=liquidity,
        holder_distribution=holder_dist,
        asset_age_days=age,
        route_snapshot=route_snapshot,
        evaluation_slot=1000
    )

@pytest.mark.asyncio
async def test_asset_blocked(admission_service, asset_id, capability_snapshot):
    # Low market cap
    snapshot = create_snapshot(asset_id, market_cap=Decimal("500000"))
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)
    assert receipt.decision == AdmissionDecision.BLOCK
    assert "LOW_MARKET_CAP" in receipt.reasons

@pytest.mark.asyncio
async def test_asset_watch(admission_service, asset_id, capability_snapshot):
    # High concentration
    snapshot = create_snapshot(asset_id, concentration=Decimal("0.30"))
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)
    assert receipt.decision == AdmissionDecision.WATCH
    assert "HIGH_CONCENTRATION" in receipt.reasons

@pytest.mark.asyncio
async def test_asset_approved(admission_service, asset_id, capability_snapshot):
    # All good
    snapshot = create_snapshot(asset_id)
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)
    assert receipt.decision == AdmissionDecision.ALLOW_SIMULATION
    assert len(receipt.reasons) == 0

@pytest.mark.asyncio
async def test_admission_hash_replay(admission_service, asset_id, capability_snapshot):
    snapshot = create_snapshot(asset_id)
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)

    # Replay with same snapshot and receipt
    replayed_receipt = await admission_service.admit_asset(snapshot, capability_snapshot, is_replay=True, stored_receipt=receipt)
    assert replayed_receipt.decision_hash == receipt.decision_hash

    # Replay with modified snapshot should fail
    modified_snapshot = snapshot.model_copy(update={"market_cap": Decimal("3000000")})
    with pytest.raises(ValueError, match="hash mismatch"):
        await admission_service.admit_asset(modified_snapshot, capability_snapshot, is_replay=True, stored_receipt=receipt)

def test_policy_determinism(asset_id):
    policy = AssetAdmissionPolicy()
    snapshot = create_snapshot(asset_id)
    caps = CapabilitySnapshot(
        execution_mode="SIMULATION",
        rpc_permissions=[],
        simulation_enabled=True,
        signing_enabled=False,
        broadcast_enabled=False
    )

    decision1, reasons1 = policy.evaluate(MarketQualityDecision.APPROVED, snapshot, caps)
    decision2, reasons2 = policy.evaluate(MarketQualityDecision.APPROVED, snapshot, caps)

    assert decision1 == decision2
    assert reasons1 == reasons2

@pytest.mark.asyncio
async def test_unknown_asset_not_approved(admission_service, asset_id, capability_snapshot):
    # Placeholder/Empty snapshot
    snapshot = AssetSnapshot(
        asset_id=asset_id,
        symbol=asset_id.symbol,
        venue=asset_id.venue,
        market_cap=Decimal("0"),
        liquidity=Decimal("0"),
        asset_age_days=0,
        evaluation_slot=1000
    )
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)
    assert receipt.decision == AdmissionDecision.BLOCK # Should be blocked due to low values

@pytest.mark.asyncio
async def test_admission_no_execution(admission_service, asset_id, capability_snapshot):
    snapshot = create_snapshot(asset_id)
    receipt = await admission_service.admit_asset(snapshot, capability_snapshot)
    # Ensure no execution related fields are present (by design of the model)
    assert receipt.decision in [AdmissionDecision.ALLOW_SIMULATION, AdmissionDecision.WATCH, AdmissionDecision.BLOCK]
    assert receipt.decision != "EXECUTE"
