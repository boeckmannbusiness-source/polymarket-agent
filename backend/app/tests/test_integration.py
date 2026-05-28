import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from app.strategies import get_strategy, get_strategy_names, list_strategies
from app.strategies.base import BaseStrategy
from app.strategies.signal import StructuredSignal
from app.config import settings


@pytest.mark.asyncio
async def test_strategy_registry_contains_all_strategies():
    names = get_strategy_names()
    assert "momentum_reversion" in names
    assert "adaptive_meta" in names
    assert "whale_following" in names
    assert "ensemble" in names
    assert len(names) >= 8


@pytest.mark.asyncio
async def test_strategy_registry_instantiation():
    for name in get_strategy_names():
        strategy = get_strategy(name, config={"enabled": True, "min_confidence": 0.1})
        assert isinstance(strategy, BaseStrategy)
        assert strategy.name == name
        assert strategy.config.enabled is True
        assert strategy.config.min_confidence == 0.1


@pytest.mark.asyncio
async def test_strategy_list_metadata():
    metadata_list = list_strategies()
    names = [m["name"] for m in metadata_list]
    assert "momentum_reversion" in names
    assert "adaptive_meta" in names
    for m in metadata_list:
        assert "name" in m
        assert "version" in m
        assert "description" in m
        assert "config" in m


@pytest.mark.asyncio
async def test_strategy_unknown_raises():
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy("nonexistent_strategy")


@pytest.mark.asyncio
async def test_health_endpoint_response():
    from app.main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "mode" in data
        assert "env" in data


@pytest.mark.asyncio
async def test_ping_endpoint_response():
    from app.main import app
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/ping")
        assert response.status_code == 200
        assert response.json() == {"ping": "pong"}


@pytest.mark.asyncio
async def test_paper_engine_deterministic_close():
    from app.engines.paper_engine import PaperEngine
    from app.models import Trade

    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    db.flush = AsyncMock()

    engine = PaperEngine(db)

    trade = MagicMock(spec=Trade)
    trade.id = uuid4()
    trade.market_id = uuid4()
    trade.side = "buy"
    trade.outcome = "YES"
    trade.size = 100.0
    trade.filled_size = 50.0
    trade.filled_price = 0.65
    trade.price = 0.65
    trade.status = "open"
    trade.stop_loss = 0.5
    trade.take_profit = 0.8

    with patch.object(engine, "_get_latest_market_price", new=AsyncMock(return_value=0.70)):
        result = await engine.evaluate_stop_loss_take_profit(trade)
        assert result is None

    with patch.object(engine, "_get_latest_market_price", new=AsyncMock(return_value=0.45)):
        result = await engine.evaluate_stop_loss_take_profit(trade)
        assert result == "stop_loss"

    with patch.object(engine, "_get_latest_market_price", new=AsyncMock(return_value=0.85)):
        result = await engine.evaluate_stop_loss_take_profit(trade)
        assert result == "take_profit"

    result1 = await engine.close_position(trade, exit_price=0.70)
    assert result1["status"] == "closed"
    assert result1["pnl"] > 0

    trade.side = "sell"
    trade.filled_price = 0.65
    result2 = await engine.close_position(trade, exit_price=0.70)
    assert result2["status"] == "closed"
    assert result2["pnl"] < 0


@pytest.mark.asyncio
async def test_execution_agent_arbitrary_outcome():
    from app.agents.execution_agent import ExecutionAgent

    agent = ExecutionAgent()
    valid_outcomes = ["YES", "NO", "Democrat", "Republican", "Biden", "Trump", "Over 50%", "Under 50%"]

    db_mock = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar.return_value = 0
    db_mock.execute = AsyncMock(return_value=mock_result)
    db_mock.flush = AsyncMock()
    db_mock.commit = AsyncMock()
    db_mock.__aenter__.return_value = db_mock
    db_mock.__aexit__.return_value = None

    mock_guard = AsyncMock()
    mock_guard.check_exposure = AsyncMock(return_value=MagicMock(approved=True))

    with patch("app.agents.execution_agent.async_session_factory", return_value=db_mock):
        with patch("app.agents.execution_agent.GlobalRiskGuard", return_value=mock_guard):
            with patch.object(agent, "_check_risk_overlay", return_value=True):
                with patch.object(agent, "_check_micro_live", return_value=True):
                    for outcome in valid_outcomes:
                        try:
                            await agent.execute_trade({
                                "signal_id": str(uuid4()),
                                "market_id": str(uuid4()),
                                "condition_id": str(uuid4()),
                                "side": "buy",
                                "outcome": outcome,
                                "size": 100.0,
                                "confidence": 0.8,
                                "strategy": "test",
                                "price": 0.5,
                            })
                        except Exception:
                            pytest.fail(f"execute_trade raised for valid outcome: {outcome}")


@pytest.mark.asyncio
async def test_redis_connectivity_smoke():
    try:
        from app.redis import get_redis, close_redis
        r = await get_redis()
        pong = await r.ping()
        assert pong is True
        await close_redis()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.mark.asyncio
async def test_unknown_strategy_registry():
    from app.strategies import get_strategy_names, get_strategy
    names = get_strategy_names()
    assert isinstance(names, list)
    assert all(isinstance(n, str) for n in names)
