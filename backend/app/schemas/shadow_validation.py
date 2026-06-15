from pydantic import BaseModel


class ValidationStatsResponse(BaseModel):
    total_signals: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    net_roi_pct: float | None = 0.0
    profit_factor: float | None = None
    win_rate_pct: float | None = 0.0


class StrategyPerformanceResponse(BaseModel):
    strategy: str
    positions: int = 0
    win_rate_pct: float = 0.0
    avg_return_pct: float = 0.0
    net_pnl_usd: float = 0.0


class ConcentrationResponse(BaseModel):
    top_wallet_share_pct: float | None = None
    top_5_wallet_share_pct: float | None = None


class TopWalletResponse(BaseModel):
    wallet: str
    pnl: float = 0.0
    win_rate: float = 0.0


class WalletUniverseResponse(BaseModel):
    observed_wallets: int = 0
    active_wallets: int = 0
    activation_rate_pct: float = 0.0
    top_wallets: list[TopWalletResponse] = []
