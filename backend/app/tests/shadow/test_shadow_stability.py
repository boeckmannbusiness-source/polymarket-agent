import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shadow.shadow_ledger import ShadowLedger
from app.services.shadow.outcome_evaluator import OutcomeEvaluator
from app.models.shadow_decision_log import ShadowDecisionLog

@pytest.mark.asyncio
async def test_decision_determinism(db_session: AsyncSession):
    """
    Verifies that equivalent inputs produce equivalent shadow decisions.
    """
    ledger = ShadowLedger(db_session)

    market_id = "market_123"
    signal_id = str(uuid.uuid4())
    strategy_id = "strat_alpha"
    confidence = 0.85
    decision = "BUY"
    size = 1000.0
    price = 1.23
    ev = 50.0
    replay_hash = "hash_abc_123"
    cert_version = "1.0.0"

    # Record first decision
    d1 = await ledger.record_decision(
        market_id=market_id,
        signal_id=signal_id,
        strategy_id=strategy_id,
        confidence=confidence,
        decision=decision,
        simulated_size=size,
        simulated_entry_price=price,
        expected_ev=ev,
        replay_hash=replay_hash,
        replay_match=True,
        certification_version=cert_version
    )

    # Record second decision with identical inputs
    d2 = await ledger.record_decision(
        market_id=market_id,
        signal_id=signal_id,
        strategy_id=strategy_id,
        confidence=confidence,
        decision=decision,
        simulated_size=size,
        simulated_entry_price=price,
        expected_ev=ev,
        replay_hash=replay_hash,
        replay_match=True,
        certification_version=cert_version
    )

    # Core decision data must match
    assert d1.market_id == d2.market_id
    assert d1.strategy_id == d2.strategy_id
    assert d1.confidence == d2.confidence
    assert d1.decision == d2.decision
    assert d1.simulated_size == d2.simulated_size
    assert d1.expected_ev == d2.expected_ev
    assert d1.replay_hash == d2.replay_hash

@pytest.mark.asyncio
async def test_outcome_stability(db_session: AsyncSession):
    """
    Verifies that updating outcomes is stable and correctly recorded.
    """
    ledger = ShadowLedger(db_session)
    evaluator = OutcomeEvaluator(db_session)

    d = await ledger.record_decision(
        market_id="m1", signal_id="s1", strategy_id="strat_stable",
        confidence=0.7, decision="BUY", simulated_size=100.0,
        simulated_entry_price=1.0, expected_ev=10.0,
        replay_hash="h1", replay_match=True, certification_version="1.0"
    )

    # Update with outcome
    await ledger.update_outcome(d.id, simulated_exit_price=1.1, actual_ev=10.0)

    # Evaluate
    metrics = await evaluator.evaluate_strategy("strat_stable")

    assert metrics["total_decisions"] == 1
    assert metrics["win_rate"] == 1.0
    assert metrics["realized_ev"] == 10.0

@pytest.mark.asyncio
async def test_confidence_drift_detection(db_session: AsyncSession):
    """
    Ensures the system can detect when confidence is poorly calibrated.
    """
    ledger = ShadowLedger(db_session)
    evaluator = OutcomeEvaluator(db_session)

    # Record 10 decisions with 90% confidence that all lose
    # This represents high confidence drift/miscalibration
    for i in range(10):
        d = await ledger.record_decision(
            market_id=f"m_{i}", signal_id=f"s_{i}", strategy_id="strat_drift",
            confidence=0.9, decision="BUY", simulated_size=100.0,
            simulated_entry_price=1.0, expected_ev=20.0,
            replay_hash=f"h_{i}", replay_match=True, certification_version="1.0"
        )
        await ledger.update_outcome(d.id, simulated_exit_price=0.5, actual_ev=-50.0)

    metrics = await evaluator.evaluate_strategy("strat_drift")

    # With 90% confidence and 0% win rate, confidence error should be high
    # (0.9 - 0)^2 = 0.81 per decision
    assert metrics["confidence_error"] == pytest.approx(0.81)
    assert metrics["win_rate"] == 0.0
