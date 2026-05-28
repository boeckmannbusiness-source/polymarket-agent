import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.risk_service import RiskService, RiskCheckResult
from app.config import settings


@pytest.mark.asyncio
async def test_low_confidence_rejected():
    db = AsyncMock()
    service = RiskService(db)
    result = await service.validate_trade(
        market_id="00000000-0000-0000-0000-000000000001",
        side="buy",
        size=100,
        confidence=0.3,
    )
    assert not result.approved
    assert "confidence" in (result.reason or "").lower()


@pytest.mark.asyncio
async def test_missing_market_id_rejected():
    db = AsyncMock()
    service = RiskService(db)
    result = await service.validate_trade(
        market_id=None,
        side="buy",
        size=100,
        confidence=0.95,
    )
    assert not result.approved
    assert "market_id" in (result.reason or "").lower()


@pytest.mark.asyncio
async def test_high_confidence_passes_initial_checks():
    db = AsyncMock()
    db.execute = AsyncMock()

    from sqlalchemy import select, func
    from uuid import UUID

    mock_count = MagicMock()
    mock_count.scalar.return_value = 0
    mock_count.scalar_one_or_none.return_value = None

    async def mock_execute(q):
        return mock_count

    db.execute = mock_execute

    service = RiskService(db)
    result = await service.validate_trade(
        market_id=UUID("00000000-0000-0000-0000-000000000001"),
        side="buy",
        size=100,
        confidence=0.95,
    )
    assert result.approved is True
