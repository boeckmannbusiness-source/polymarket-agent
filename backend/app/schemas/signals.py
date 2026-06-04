from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Any


class ResearchSignal(BaseModel):
    signal_id: str = ""
    agent_id: str = ""
    agent_name: str = ""
    market_id: str = ""
    market_title: str = ""
    direction: str = ""  # buy|sell
    outcome: str = ""  # YES|NO
    confidence: float = 0.0
    rationale: str = ""
    evidence: list[dict[str, Any]] = []
    created_at: str = ""


class SignalScore(BaseModel):
    signal_id: str = ""
    confidence_score: float = 0.0
    evidence_score: float = 0.0
    novelty_score: float = 0.0
    historical_accuracy_score: float = 0.0
    composite_score: float = 0.0


class AgentHealth(BaseModel):
    agent_id: str
    agent_name: str
    status: str = "healthy"  # healthy|degraded|down
    signals_generated: int = 0
    historical_accuracy: float = 0.0
    contribution_score: float = 0.0
    last_run: str = ""
    error_message: str = ""


class ConsensusResult(BaseModel):
    signal: ResearchSignal | None = None
    supporting_agents: list[dict[str, Any]] = []
    opposing_agents: list[dict[str, Any]] = []
    consensus_score: float = 0.0
    consensus_type: str = ""  # majority|weighted_confidence|weighted_accuracy|challenger_override
    approved: bool = False
    created_at: str = ""


class RegistryEntry(BaseModel):
    signal_id: str
    agent_id: str
    agent_name: str
    market_id: str
    direction: str
    outcome: str
    confidence: float
    quality_score: float = 0.0
    composite_score: float = 0.0
    lifecycle: str = "generated"  # generated|scored|meta_reviewed|consensus_approved|consensus_rejected|in_shadow|promoted
    promotion_state: str = "none"
    created_at: str = ""
    updated_at: str = ""


class SignalSummary(BaseModel):
    total_signals: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    pending_count: int = 0
    avg_confidence: float = 0.0
    avg_quality: float = 0.0


class AgentSignalCount(BaseModel):
    agent_id: str
    agent_name: str
    total: int = 0
    approved: int = 0
    rejected: int = 0