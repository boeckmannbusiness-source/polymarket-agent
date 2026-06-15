from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.system import _require_admin
from app.core.metrics import solana_validation_requests_total
from app.database import get_db
from app.models.research_trade import ResearchTrade
from app.models.smart_wallet import SmartWallet
from app.repositories.research_trade_repository import ResearchTradeRepository
from app.repositories.wallet_trade_repository import WalletTradeRepository
from app.schemas.shadow_validation import (
    ConcentrationResponse,
    StrategyPerformanceResponse,
    ValidationStatsResponse,
    WalletUniverseResponse,
)
from app.services.shadow_validation_service import ShadowValidationService
from app.services.wallet_scoring_service import WalletScoringService

router = APIRouter()


class SolanaSignalResponse(BaseModel):
    id: UUID
    signal_id: str | None
    strategy: str
    entry_price: float
    confidence: float | None
    status: str
    opened_at: str
    created_at: str | None = None
    wallet_address: str | None = None
    wallet_score: float | None = None
    wallet_score_1h: float | None = None
    wallet_score_24h: float | None = None
    wallet_confidence: float | None = None
    wallet_classification: str | None = None

    model_config = {"from_attributes": True}


def _to_response(t: ResearchTrade, wallet_scores: dict[str, dict] | None = None) -> SolanaSignalResponse:
    wallet_address = None
    ws = None
    if t.wallet_trade and t.wallet_trade.wallet:
        w = t.wallet_trade.wallet
        wallet_address = w.wallet_address
        if wallet_scores and wallet_address in wallet_scores:
            ws = wallet_scores[wallet_address]

    return SolanaSignalResponse(
        id=t.id,
        signal_id=t.signal_id,
        strategy=t.strategy,
        entry_price=float(t.entry_price) if t.entry_price is not None else 0.0,
        confidence=float(t.confidence) if t.confidence is not None else None,
        status=t.status,
        opened_at=t.opened_at.isoformat() if t.opened_at else "",
        created_at=t.created_at.isoformat() if t.created_at else None,
        wallet_address=wallet_address,
        wallet_score=ws["score"] if ws else None,
        wallet_score_1h=ws["score_1h"] if ws else None,
        wallet_score_24h=ws["score_24h"] if ws else None,
        wallet_confidence=ws["confidence"] if ws else None,
        wallet_classification=ws["classification"] if ws else None,
    )


async def _build_wallet_score_map(trades: list[ResearchTrade], scoring_svc: WalletScoringService, db: AsyncSession) -> dict[str, dict]:
    wallet_ids = set()
    for t in trades:
        if t.wallet_trade and t.wallet_trade.wallet:
            wallet_ids.add(t.wallet_trade.wallet.wallet_address)
    if not wallet_ids:
        return {}

    wtr = WalletTradeRepository(db)
    all_metrics = await wtr.aggregate_wallet_metrics()
    scored = scoring_svc.compute_scores_batch(all_metrics)
    return {s["wallet_address"]: s for s in scored if s["wallet_address"] in wallet_ids}


@router.get("")
async def list_solana_signals(
    skip: int = 0,
    limit: int = 50,
    strategy: str | None = Query(None),
    status: str | None = Query(None),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> list[SolanaSignalResponse]:
    repo = ResearchTradeRepository(db)
    if status == "open":
        trades = await repo.list_open_positions(strategy=strategy, limit=None)
    elif strategy:
        trades = await repo.list_by_strategy(strategy, limit=None)
    else:
        trades = await repo.list_all(limit=None)

    scoring_svc = WalletScoringService()
    wallet_scores = await _build_wallet_score_map(trades, scoring_svc, db)

    results = [_to_response(t, wallet_scores) for t in trades]
    if min_confidence is not None:
        results = [r for r in results if (r.wallet_confidence or 0.0) >= min_confidence]
    results.sort(key=lambda r: (-1 * (r.wallet_score or 0.0), r.wallet_address or ""))
    return results[skip:skip + limit]


@router.get("/stats")
async def get_validation_stats(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> ValidationStatsResponse:
    svc = ShadowValidationService(db)
    result = await svc.get_stats()
    solana_validation_requests_total.labels(endpoint="stats").inc()
    return result


@router.get("/performance")
async def get_strategy_performance(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> list[StrategyPerformanceResponse]:
    svc = ShadowValidationService(db)
    result = await svc.get_performance()
    solana_validation_requests_total.labels(endpoint="performance").inc()
    return result


@router.get("/concentration")
async def get_concentration(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> ConcentrationResponse:
    svc = ShadowValidationService(db)
    result = await svc.get_concentration()
    solana_validation_requests_total.labels(endpoint="concentration").inc()
    return result


@router.get("/wallet-universe")
async def get_wallet_universe(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> WalletUniverseResponse:
    svc = ShadowValidationService(db)
    result = await svc.get_wallet_universe()
    solana_validation_requests_total.labels(endpoint="wallet-universe").inc()
    return result


@router.get("/{signal_id}")
async def get_solana_signal(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(_require_admin),
) -> SolanaSignalResponse:
    repo = ResearchTradeRepository(db)
    trade = await repo.get_by_id(signal_id)
    scoring_svc = WalletScoringService()
    wallet_scores = await _build_wallet_score_map([trade], scoring_svc, db) if trade else {}
    return _to_response(trade, wallet_scores)
