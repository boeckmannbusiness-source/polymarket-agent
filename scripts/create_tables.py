import asyncio
from app.database import engine
from app.models.market import Market
from app.models.wallet import Wallet, WalletTrade, WalletScore, WalletCluster
from app.models.signal import Signal
from app.models.trade import Trade
from app.models.backtest import BacktestRun, BacktestTrade
from app.models.agent_log import AgentLog
from app.models.strategy import StrategyConfigRecord, StrategyPerformanceRecord
from app.models.signal_outcome import SignalOutcome
from app.models.market_snapshot import MarketStateSnapshot
from app.models.portfolio import Position, PortfolioSnapshot, MarketCorrelation
from app.models.feature_store import FeatureSchemaVersion, FeatureLineage
from app.models.safety import SafetyState
from app.models.execution_trace import ExecutionTrace
from app.models.trade_attribution import TradeAttribution
from app.models.strategy_allocation import StrategyAllocationState
from app.models.system_mode import SystemModeTransition
from app.models.remote_audit import RemoteControlAudit
from app.models.portfolio_audit_log import PortfolioAuditLog
from app.models.benchmark_price import BenchmarkPrice
from app.models.exchange_order import ExchangeOrder
from app.models.fill import Fill
from app.models.shadow_decision_log import ShadowDecisionLog

async def init():
    from app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")

if __name__ == "__main__":
    asyncio.run(init())
