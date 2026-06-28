import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from app.services.shadow.shadow_ledger import ShadowLedger
from app.models.shadow_decision_log import ShadowDecisionLog
from app.services.execution.execution_service import ExecutionService
from app.domain.execution import ExecutionIntent, ExecutionResult, Instrument
from app.services.shadow.outcome_engine import OutcomeClosureEngine
from app.services.shadow.evidence_engine import EvidenceEngine
from app.services.shadow.promotion_audit_service import PromotionAuditService
from app.services.shadow.promotion_readiness_service import PromotionReadinessService, ReadinessStatus
from app.services.shadow.dashboard_service import DashboardService

@pytest.mark.asyncio
async def test_shadow_decision_persistence(db_session):
    ledger = ShadowLedger(db_session)

    # Record a decision
    decision = await ledger.record_decision(
        market_id="test_market",
        signal_id="test_signal",
        strategy_id="test_strat",
        confidence=0.8,
        decision="buy",
        simulated_size=100.0,
        simulated_entry_price=0.5,
        expected_ev=10.0,
        replay_hash="hash123",
        replay_match=True,
        certification_version="8.3",
        predicted_direction="buy",
        execution_hash="exec123",
        snapshot_hash="snap123"
    )

    assert decision.id is not None
    assert decision.decision_status == "OPEN"
    assert decision.predicted_direction == "buy"
    assert decision.execution_hash == "exec123"
    assert decision.snapshot_hash == "snap123"

@pytest.mark.asyncio
async def test_shadow_resolution_lifecycle(db_session):
    ledger = ShadowLedger(db_session)
    outcome_engine = OutcomeClosureEngine(db_session)

    # 1. Create OPEN decision
    decision = await ledger.record_decision(
        market_id="test_market",
        signal_id="test_signal",
        strategy_id="test_strat",
        confidence=0.8,
        decision="buy",
        simulated_size=100.0,
        simulated_entry_price=0.5,
        expected_ev=10.0,
        replay_hash="hash123",
        replay_match=True,
        certification_version="8.3"
    )

    assert decision.decision_status == "OPEN"

    # 2. Resolve decision
    receipt = await outcome_engine.resolve_decision(
        decision_id=decision.id,
        resolution_price=0.6,
        resolution_source="oracle"
    )

    # Verify persistence
    assert decision.decision_status == "RESOLVED"
    assert pytest.approx(decision.realized_ev) == 10.0  # (0.6 - 0.5) * 100
    assert decision.outcome_timestamp is not None
    assert decision.market_resolution_source == "oracle"

@pytest.mark.asyncio
async def test_promotion_requires_shadow_origin(db_session):
    evidence_engine = EvidenceEngine(db_session)
    audit_service = PromotionAuditService(db_session)

    # Case 1: No decisions (synthetic by default)
    snapshot = await evidence_engine.generate_snapshot("empty_strat")
    assert snapshot.data_origin == "synthetic"

    audit = await audit_service.audit_strategy("empty_strat", snapshot=snapshot)
    assert audit["status"] == "NOT_READY"
    assert any("Promotion requires real shadow evidence" in r for r in audit["reasons"])

    # Case 2: With decisions (origin should be shadow)
    ledger = ShadowLedger(db_session)
    await ledger.record_decision(
        market_id="test_market",
        signal_id="test_signal",
        strategy_id="shadow_strat",
        confidence=0.8,
        decision="buy",
        simulated_size=100.0,
        simulated_entry_price=0.5,
        expected_ev=10.0,
        replay_hash="hash123",
        replay_match=True,
        certification_version="8.3"
    )

    snapshot = await evidence_engine.generate_snapshot("shadow_strat")
    assert snapshot.data_origin == "shadow"

@pytest.mark.asyncio
async def test_readiness_gate_blocks_premature_ready(db_session):
    readiness_service = PromotionReadinessService(db_session)
    ledger = ShadowLedger(db_session)

    # Add only 10 decisions
    for i in range(10):
        await ledger.record_decision(
            market_id="test_market",
            signal_id=f"sig_{i}",
            strategy_id="low_volume_strat",
            confidence=0.8,
            decision="buy",
            simulated_size=100.0,
            simulated_entry_price=0.5,
            expected_ev=10.0,
            replay_hash="hash123",
            replay_match=True,
            certification_version="8.3"
        )

    state = await readiness_service.get_readiness_state("low_volume_strat")
    # All are OPEN, so resolved count is 0. Status should be COLLECTING with reason AWAITING_RESOLUTION
    assert state["readiness_status"] == ReadinessStatus.COLLECTING
    assert state["readiness_reason"] == "AWAITING_RESOLUTION"

    # Resolve some
    outcome_engine = OutcomeClosureEngine(db_session)
    result = await db_session.execute(select(ShadowDecisionLog).where(ShadowDecisionLog.strategy_id == "low_volume_strat"))
    decisions = result.scalars().all()
    for d in decisions[:5]:
        await outcome_engine.resolve_decision(d.id, 0.6)

    state = await readiness_service.get_readiness_state("low_volume_strat")
    assert state["readiness_status"] == ReadinessStatus.COLLECTING
    assert state["decision_count"] == 5

    # Add up to 200 decisions and resolve them
    for i in range(200):
        d = await ledger.record_decision(
            market_id="test_market",
            signal_id=f"sig_insufficient_{i}",
            strategy_id="insufficient_strat",
            confidence=0.8,
            decision="buy",
            simulated_size=100.0,
            simulated_entry_price=0.5,
            expected_ev=10.0,
            replay_hash="hash123",
            replay_match=True,
            certification_version="8.3"
        )
        await outcome_engine.resolve_decision(d.id, 0.6)

    state = await readiness_service.get_readiness_state("insufficient_strat")
    assert state["readiness_status"] == ReadinessStatus.INSUFFICIENT_VOLUME

@pytest.mark.asyncio
async def test_dashboard_generates_health_report(db_session):
    dashboard = DashboardService(db_session)
    ledger = ShadowLedger(db_session)

    await ledger.record_decision(
        market_id="test_market",
        signal_id="test_signal",
        strategy_id="test_strat",
        confidence=0.8,
        decision="buy",
        simulated_size=100.0,
        simulated_entry_price=0.5,
        expected_ev=10.0,
        replay_hash="hash123",
        replay_match=True,
        certification_version="8.3"
    )

    # Generate reports
    await dashboard.generate_ops_report()

    import os
    assert os.path.exists("SHADOW_HEALTH_REPORT.md")

    with open("SHADOW_HEALTH_REPORT.md", "r") as f:
        content = f.read()
        assert "SHADOW_HEALTH_REPORT" in content
        assert "OPEN (Backlog) | 1" in content
        assert "Evidence Origin | shadow" in content

@pytest.mark.asyncio
async def test_empty_metrics_are_not_perfect(db_session):
    dashboard = DashboardService(db_session)
    audit_service = PromotionAuditService(db_session)

    # Empty state - ensure no decisions in DB
    await db_session.execute(ShadowDecisionLog.__table__.delete())
    await db_session.commit()

    await dashboard.generate_ops_report()

    with open("SHADOW_HEALTH_REPORT.md", "r") as f:
        content = f.read()
        assert "Replay Parity | NOT_AVAILABLE" in content
        assert "Confidence Calibration | NOT_AVAILABLE" in content

    with open("SHADOW_OPERATIONS_REPORT.md", "r") as f:
        content = f.read()
        assert "Global Replay Parity | NOT_AVAILABLE" in content
        assert "Global Brier Score | NOT_AVAILABLE" in content
        assert "Total Realized EV | NOT_AVAILABLE" in content

    audit = await audit_service.generate_promotion_report("empty_strat")
    assert "Replay Parity | NOT_AVAILABLE" in audit
    assert "Realized EV | NOT_AVAILABLE" in audit
    assert "Brier Score | NOT_AVAILABLE" in audit

@pytest.mark.asyncio
async def test_report_population_consistency(db_session):
    dashboard = DashboardService(db_session)
    ledger = ShadowLedger(db_session)
    outcome_engine = OutcomeClosureEngine(db_session)

    # Ensure fresh start
    await db_session.execute(ShadowDecisionLog.__table__.delete())
    await db_session.commit()

    # 1. OPEN
    await ledger.record_decision(
        market_id="m1", signal_id="s1", strategy_id="strat",
        confidence=0.8, decision="buy", simulated_size=100.0, simulated_entry_price=0.5,
        expected_ev=10.0, replay_hash="h1", replay_match=True, certification_version="8.3"
    )

    # 2. CLOSED (simulated by setting status)
    d2 = await ledger.record_decision(
        market_id="m2", signal_id="s2", strategy_id="strat",
        confidence=0.8, decision="buy", simulated_size=100.0, simulated_entry_price=0.5,
        expected_ev=10.0, replay_hash="h2", replay_match=True, certification_version="8.3"
    )
    d2.decision_status = "CLOSED"
    await db_session.flush()

    # 3. RESOLVED
    d3 = await ledger.record_decision(
        market_id="m3", signal_id="s3", strategy_id="strat",
        confidence=0.8, decision="buy", simulated_size=100.0, simulated_entry_price=0.5,
        expected_ev=10.0, replay_hash="h3", replay_match=True, certification_version="8.3"
    )
    await outcome_engine.resolve_decision(d3.id, 0.6)

    await dashboard.generate_ops_report()

    with open("SHADOW_HEALTH_REPORT.md", "r") as f:
        content = f.read()
        assert "Total Decisions | 3" in content
        assert "OPEN (Backlog) | 1" in content
        assert "CLOSED (Awaiting Resolution) | 1" in content
        assert "RESOLVED (Throughput) | 1" in content
