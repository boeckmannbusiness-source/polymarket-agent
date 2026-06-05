from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Any


class ResearchMemoryEntry(BaseModel):
    entry_id: str
    entry_type: str  # hypothesis_winning|hypothesis_failed|retired_strategy|promotion_history|regime|signal_effectiveness|agent_observation
    strategy_id: str | None = None
    tags: list[str] = []
    content: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = {}
    created_at: str = ""


class HypothesisRecord(BaseModel):
    hypothesis_id: str
    title: str
    description: str
    status: str = "PROPOSED"  # PROPOSED|TESTING|VALIDATED|REJECTED|ARCHIVED
    confidence: float = 0.0
    evidence: list[str] = []
    validation_metrics: dict[str, float] = {}
    tags: list[str] = []
    created_at: str = ""
    updated_at: str = ""


class RegimeSnapshot(BaseModel):
    regime: str
    confidence: float = 0.0
    indicators: dict[str, float] = {}
    detected_at: str = ""


class RegimeHistory(BaseModel):
    regimes: list[RegimeSnapshot] = []


class CandidateRecommendation(BaseModel):
    candidate_id: str
    strategy_id: str
    archetype: str
    confidence: float = 0.0
    novelty_score: float = 0.0
    diversity_score: float = 0.0
    incubation_ready: bool = False
    generated_at: str = ""


class IncubationDecision(BaseModel):
    strategy_id: str
    from_status: str = "EXPERIMENTAL"
    to_status: str = "SHADOW"
    reasons: list[str] = []
    approved: bool = False
    created_at: str = ""


class ResearchReport(BaseModel):
    report_id: str
    generated_at: str = ""
    regimes: list[RegimeSnapshot] = []
    hypotheses: list[HypothesisRecord] = []
    candidates: list[CandidateRecommendation] = []
    incubations: list[IncubationDecision] = []
    summary: str = ""
