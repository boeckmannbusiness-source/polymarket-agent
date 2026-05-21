import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.risk_service import RiskService, RiskCheckResult
from app.config import settings


@pytest.mark.asyncio
async def test_low_confidence_rejected():
    db = AsyncMock()
    service = RiskService(db)
    result = await service.validate_trade(
        market_id=None,
        side="buy",
        size=100,
        confidence=0.3,
    )
    assert not result.approved
    assert "confidence" in (result.reason or "").lower()


@pytest.mark.asyncio
async def test_high_confidence_calls_open_trades():
    db = AsyncMock()
    db.execute = AsyncMock()

    from sqlalchemy import select, func

    mock_result = MagicMock()
    mock_result.scalar.return_value = 0
    db.execute.return_value = mock_result

    service = RiskService(db)
    result = await service.validate_trade(
        market_id=None,
        side="buy",
        size=100,
        confidence=0.95,
    )
    assert result.approved is False
