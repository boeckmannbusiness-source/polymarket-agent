from datetime import datetime, timezone
from typing import Any

from app.core.logging import logger
from app.schemas.signals import ResearchSignal, RegistryEntry
from app.services.agents.news_agent import news_agent
from app.services.agents.social_agent import social_agent
from app.services.agents.prediction_agent import prediction_agent
from app.services.agents.market_microstructure_agent import micro_agent
from app.services.agents.meta_research_agent import meta_agent
from app.services.research.signal_registry import signal_registry
from app.services.research.signal_scoring_service import scoring_service
from app.services.research.signal_consensus_service import consensus_service
from app.services.incidents.incident_service import incident_service
from app.services.control.control_plane import ControlPlane
from app.services.audit.audit_logger import emit as audit_emit

_AGENTS = {
    "news": news_agent,
    "social": social_agent,
    "prediction": prediction_agent,
    "micro": micro_agent,
}

ALL_AGENTS = list(_AGENTS.values())


class ResearchOrchestrator:
    def __init__(self):
        self._last_run: str = ""
        self._run_count: int = 0

    async def run_pipeline(self) -> dict[str, Any]:
        control = ControlPlane()
        state = await control.get_state()
        if not state.get("trading_enabled", True):
            logger.info("orchestrator_skipped_trading_disabled")
            return {"status": "skipped", "reason": "trading_disabled"}

        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "agents_run": 0,
            "signals_generated": 0,
            "signals_after_meta": 0,
            "approved": 0,
            "rejected": 0,
            "errors": [],
        }

        all_signals: list[ResearchSignal] = []
        agent_scores: dict[str, dict[str, Any]] = {}

        for agent in ALL_AGENTS:
            try:
                signals = await agent.generate_signals()
                all_signals.extend(signals)
                results["agents_run"] += 1
                results["signals_generated"] += len(signals)
            except Exception as e:
                logger.error("orchestrator_agent_failed", agent=agent.agent_id, error=str(e))
                results["errors"].append(f"{agent.agent_id}: {str(e)}")

        deduped, removed = await meta_agent.review_signals(all_signals)
        results["signals_after_meta"] = len(deduped)
        results["duplicates_removed"] = len(removed)

        for signal in deduped:
            qs = await meta_agent.compute_quality_score(signal, deduped)
            entry = await signal_registry.register(signal, quality_score=qs)
            await signal_registry.update_lifecycle(signal.signal_id, "scored")

            scores = await scoring_service.compute_score(
                signal_id=signal.signal_id,
                confidence_score=signal.confidence * 100,
                evidence_score=min(100.0, len(signal.evidence) * 22.0),
                novelty_score=qs,
                historical_accuracy_score=0.0,
            )
            agent_scores[signal.agent_id] = {
                "composite_score": scores.composite_score,
                "confidence_score": scores.confidence_score,
            }

            await signal_registry.update_lifecycle(signal.signal_id, "meta_reviewed")

        for signal in deduped:
            result = await consensus_service.compute_consensus(signal, deduped, agent_scores)
            if result.approved:
                await signal_registry.update_lifecycle(signal.signal_id, "consensus_approved")
                results["approved"] += 1
                self._push_to_shadow(signal)
            else:
                await signal_registry.update_lifecycle(signal.signal_id, "consensus_rejected")
                results["rejected"] += 1

        self._last_run = datetime.now(timezone.utc).isoformat()
        self._run_count += 1
        results["completed_at"] = self._last_run
        results["run_count"] = self._run_count

        await audit_emit("orchestrator.run", "orchestrator", "research", {
            "signals_generated": results["signals_generated"],
            "approved": results["approved"],
            "rejected": results["rejected"],
            "duplicates_removed": results.get("duplicates_removed", 0),
            "agents_run": results["agents_run"],
        })

        logger.info("orchestrator_completed", signals=results["signals_generated"], approved=results["approved"], rejected=results["rejected"])
        return results

    def _push_to_shadow(self, signal: ResearchSignal):
        try:
            from app.services.shadow.shadow_execution_service import shadow_execution_service
            import asyncio
            asyncio.ensure_future(shadow_execution_service.process_signal({
                "id": signal.signal_id,
                "market_id": signal.market_id,
                "source_agent": f"research:{signal.agent_id}",
                "direction": signal.direction,
                "outcome": signal.outcome,
                "confidence": signal.confidence,
                "estimated_probability": 0.5,
            }))
        except Exception as e:
            logger.error("orchestrator_push_to_shadow_failed", signal_id=signal.signal_id, error=str(e))

    async def get_status(self) -> dict[str, Any]:
        stats = await signal_registry.get_stats()
        return {
            "last_run": self._last_run,
            "run_count": self._run_count,
            "stats": stats,
        }

    async def get_agent_health(self) -> list[dict[str, Any]]:
        results = []
        for agent in ALL_AGENTS:
            try:
                h = await agent.health_check()
                results.append(h)
            except Exception as e:
                results.append({"agent_id": agent.agent_id, "status": "down", "error": str(e)})
        return results

    async def reset(self):
        await signal_registry.reset()
        self._last_run = ""
        self._run_count = 0


orchestrator = ResearchOrchestrator()