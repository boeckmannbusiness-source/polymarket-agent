import pytest
import uuid
from decimal import Decimal
from app.models.trade import Trade
from app.models.fill import Fill
from app.domain.execution import ExecutionIntent, Instrument
from app.services.execution.intent_factory import ExecutionIntentFactory
from app.services.shadow.shadow_execution_service import ShadowExecutionService


def test_trade_model_venue_neutrality():
    """Verify Trade model supports both UUID and string market IDs and has no required outcome."""
    # Polymarket style (UUID)
    trade_poly = Trade(
        id=uuid.uuid4(),
        market_id=str(uuid.uuid4()),
        side="buy",
        outcome="YES",
        size=10.0
    )
    assert trade_poly.outcome == "YES"

    # Solana style (String Mint Address)
    trade_sol = Trade(
        id=uuid.uuid4(),
        market_id="So11111111111111111111111111111111111111112",
        side="buy",
        outcome=None, # Solana trades don't have binary outcomes
        size=1.5
    )
    assert trade_sol.outcome is None
    assert trade_sol.market_id == "So11111111111111111111111111111111111111112"


def test_fill_model_venue_neutrality():
    """Verify Fill model supports string market IDs and nullable outcome."""
    fill = Fill(
        id=uuid.uuid4(),
        exchange_order_id=uuid.uuid4(),
        trade_id=uuid.uuid4(),
        market_id="So11111111111111111111111111111111111111112",
        fill_num=1,
        side="buy",
        outcome=None,
        size=Decimal("1.5"),
        price=Decimal("0.5"),
        filled_at=pytest.importorskip("datetime").datetime.utcnow()
    )
    assert fill.market_id == "So11111111111111111111111111111111111111112"
    assert fill.outcome is None


def test_execution_intent_no_outcome_leakage():
    """Verify ExecutionIntent is decoupled from outcome semantics."""
    trade = Trade(
        id=uuid.uuid4(),
        market_id="So11111111111111111111111111111111111111112",
        side="buy",
        outcome=None,
        size=1.5,
        trade_type="solana"
    )

    intent = ExecutionIntentFactory.create_from_trade(trade, engine_type="jupiter")

    # Core intent should not have outcome in metadata
    assert intent.instrument.metadata is None
    # Outcome only exists in compatibility layer
    assert intent.compat_outcome is None

    # Polymarket compatibility
    trade_poly = Trade(
        id=uuid.uuid4(),
        market_id=str(uuid.uuid4()),
        side="buy",
        outcome="YES",
        size=10.0,
        trade_type="paper"
    )
    intent_poly = ExecutionIntentFactory.create_from_trade(trade_poly, engine_type="paper")
    assert intent_poly.compat_outcome == "YES"
    # Instrument metadata should STILL be clean to avoid leakage
    assert intent_poly.instrument.metadata is None


@pytest.mark.asyncio
async def test_shadow_layer_neutrality():
    """Verify shadow layer handles both SOL/USDC and YES/NO without binary logic."""
    service = ShadowExecutionService()

    # Solana Shadow Trade
    signal_sol = {
        "id": uuid.uuid4(),
        "market_id": "So11111111111111111111111111111111111111112",
        "price": 145.50,
        "direction": "buy",
        "confidence": 0.8,
        "source_agent": "solana_whale"
    }
    exec_sol = await service.process_signal(signal_sol)
    assert exec_sol.outcome == "NONE"
    assert exec_sol.entry_price == 145.50

    # Polymarket Shadow Trade
    signal_poly = {
        "id": uuid.uuid4(),
        "market_id": str(uuid.uuid4()),
        "estimated_probability": 0.65,
        "direction": "buy",
        "outcome": "YES",
        "confidence": 0.7,
        "source_agent": "poly_agent"
    }
    exec_poly = await service.process_signal(signal_poly)
    assert exec_poly.outcome == "YES"
    assert exec_poly.entry_price == 0.65
