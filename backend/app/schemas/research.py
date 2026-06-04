from pydantic import BaseModel
from datetime import datetime
from typing import Any


class StrategyMetadata(BaseModel):
    strategy_id: str
    name: str
    version: int = 1
    owner: str = "unknown"
    status: str = "experimental"  # experimental|shadow|paper|live|retired
    created_at: str = ""
    promoted_at: str | None = None
    retired_at: str | None = None
    predecessor: str | None = None
    successor: str | None = None
    notes: str = ""


class ChampionResult(BaseModel):
    champion: str | None = None
    champion_score: float = 0.0
    challengers: list[dict[str, Any]] = []
    replacement_score: float = 0.0
    recommendation: str = "KEEP"


class StrategyHealth(BaseModel):
    strategy: str
    score: float = 100.0
    level: str = "HEALTHY"  # HEALTHY|WARNING|CRITICAL
    pnl_trend: float = 0.0
    drawdown_trend: float = 0.0
    win_rate_trend: float = 0.0
    latency_incidents: int = 0
    breaker_events: int = 0
    drift_events: int = 0
    execution_failures: int = 0
    history_7d: list[float] = []
    history_30d: list[float] = []
    history_lifetime: list[float] = []


class ResearchReport(BaseModel):
    strategy: str
    generated_at: str = ""
    performance_summary: dict[str, Any] = {}
    strengths: list[str] = []
    weaknesses: list[str] = []
    benchmark_comparison: dict[str, Any] = {}
    promotion_recommendation: dict[str, Any] = {}
    risk_factors: list[str] = []


class PortfolioReport(BaseModel):
    generated_at: str = ""
    total_strategies: int = 0
    top_performers: list[dict[str, Any]] = []
    worst_performers: list[dict[str, Any]] = []
    concentration_risks: list[dict[str, Any]] = []
    promotion_opportunities: list[dict[str, Any]] = []
    retirement_candidates: list[dict[str, Any]] = []
