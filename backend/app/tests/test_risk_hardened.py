import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.trade_service import TradeService
from app.schemas.trade import TradeCreateRequest
from app.core.exceptions import TradeExecutionError, MarketNotFoundError
from app.models import Market

@pytest.mark.asyncio
async def test_confidence_handling_none(db_session):
    service = TradeService(db_session)
    # Mock dependencies
    service.safety_service.check_trade_approval = AsyncMock(return_value=MagicMock(approved=True))
    service.risk_service.validate_trade = AsyncMock(return_value=MagicMock(approved=True))

    # Mock Market so it doesn't fail there
    mock_market = MagicMock()

    request = TradeCreateRequest(
        market_id=uuid4(),
        side="buy",
        outcome="YES",
        size=10.0,
        confidence=None,
        agent_id="test"
    )

    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_exec:
        # First call is for Market check
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        # Second call is for duplicate check
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None

        mock_exec.side_effect = [mock_result, mock_result2]

        try:
            await service.create_trade(request)
        except Exception:
            pass

    # Verify that confidence=None was resolved to 0.0 at the entry point
    # and passed as 0.0 to all downstream services.
    service.safety_service.check_trade_approval.assert_called_with(
        strategy_name="test",
        size=10.0,
        confidence=0.0
    )
    service.risk_service.validate_trade.assert_called_with(
        market_id=request.market_id,
        side="buy",
        size=10.0,
        confidence=0.0,
        agent_id="test"
    )

@pytest.mark.asyncio
async def test_confidence_handling_zero(db_session):
    service = TradeService(db_session)
    service.safety_service.check_trade_approval = AsyncMock(return_value=MagicMock(approved=True))
    service.risk_service.validate_trade = AsyncMock(return_value=MagicMock(approved=True))

    request = TradeCreateRequest(
        market_id=uuid4(),
        side="buy",
        outcome="YES",
        size=10.0,
        confidence=0.0,
        agent_id="test"
    )

    try:
        await service.create_trade(request)
    except Exception:
        pass

    # Verify that confidence=0.0 was preserved
    service.safety_service.check_trade_approval.assert_called_with(
        strategy_name="test",
        size=10.0,
        confidence=0.0
    )

@pytest.mark.asyncio
async def test_confidence_below_threshold(db_session):
    service = TradeService(db_session)
    service.safety_service.check_trade_approval = AsyncMock(return_value=MagicMock(approved=True))

    # Mock Market
    mock_market = MagicMock()

    request = TradeCreateRequest(
        market_id=uuid4(),
        side="buy",
        outcome="YES",
        size=10.0,
        confidence=0.1, # Definitely below 0.6
        agent_id="test"
    )

    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_exec:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_market
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = None
        mock_exec.side_effect = [mock_result, mock_result2]

        with pytest.raises(TradeExecutionError, match="Risk check failed"):
            await service.create_trade(request)
