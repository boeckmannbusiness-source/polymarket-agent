import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.services.trade_service import TradeService
from app.schemas.trade import TradeCreateRequest
from app.core.exceptions import TradeExecutionError
from app.services.portfolio_allocator import AllocatedPosition

@pytest.mark.asyncio
async def test_confidence_propagation_pipeline(db_session):
    service = TradeService(db_session)

    # Mock SafetyService, and the ValidationEngine to ensure we reach Allocation
    service.safety_service.check_trade_approval = AsyncMock(return_value=MagicMock(approved=True))

    # Define test cases: (input_confidence, expected_resolved)
    test_cases = [
        (0.0, 0.0),
        (None, 0.0),
        (0.59, 0.59),
        (0.60, 0.60),
        (0.95, 0.95),
    ]

    for input_conf, expected_resolved in test_cases:
        request = TradeCreateRequest(
            market_id=uuid4(),
            side="buy",
            outcome="YES",
            size=100.0,
            confidence=input_conf,
            agent_id="test_agent"
        )

        service.safety_service.check_trade_approval.reset_mock()

        # Mock Market check in create_trade
        with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_exec:
            mock_mkt_result = MagicMock()
            mock_mkt_result.scalar_one_or_none.return_value = MagicMock() # Found market

            mock_dup_result = MagicMock()
            mock_dup_result.scalar_one_or_none.return_value = None # No duplicate

            mock_exec.side_effect = [mock_mkt_result, mock_dup_result]

            # Mock ValidationEngine to always approve
            with patch("app.services.validation_engine.ValidationEngine.validate_trade",
                       new=AsyncMock(return_value=MagicMock(approved=True, reasons=[]))):

                # Mock PortfolioAllocator
                with patch("app.services.portfolio_allocator.PortfolioAllocator.allocate",
                           new=AsyncMock(return_value=AllocatedPosition(size=10.0, risk_weight=0.5, exposure_bucket="core"))) as mock_allocate:

                    try:
                        await service.create_trade(request)
                    except Exception:
                        pass

                    # 1. Verify SafetyService saw the resolved confidence
                    service.safety_service.check_trade_approval.assert_called_once()
                    assert service.safety_service.check_trade_approval.call_args[1]['confidence'] == expected_resolved

                    # 2. Verify PortfolioAllocator saw the EXACT same resolved confidence
                    mock_allocate.assert_called_once()
                    assert mock_allocate.call_args[1]['signal_confidence'] == expected_resolved

@pytest.mark.asyncio
async def test_allocation_sensitivity_to_confidence(db_session):
    from app.services.portfolio_allocator import PortfolioAllocator
    allocator = PortfolioAllocator(db_session)

    # High confidence (0.95)
    res_high = await allocator.allocate(0.95, "test", "high_liquidity", "normal", 0.0)
    # Mid confidence (0.75)
    res_mid = await allocator.allocate(0.75, "test", "high_liquidity", "normal", 0.0)
    # Low confidence (0.55)
    res_low = await allocator.allocate(0.55, "test", "high_liquidity", "normal", 0.0)
    # Very low confidence (0.10)
    res_min = await allocator.allocate(0.10, "test", "high_liquidity", "normal", 0.0)

    assert res_high.confidence_factor == 1.0
    assert res_mid.confidence_factor == 0.8
    assert res_low.confidence_factor == 0.5
    assert res_min.confidence_factor == 0.25

    assert res_high.size > res_mid.size > res_low.size > res_min.size
