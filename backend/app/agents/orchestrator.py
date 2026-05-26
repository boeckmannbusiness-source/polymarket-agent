import asyncio

from app.agents.base import BaseAgent
from app.config import settings
from app.core.logging import logger
from app.core.events import EventBus


class Orchestrator:
    def __init__(self):
        from app.agents.whale_agent import WhaleAgent
        from app.agents.signal_agent import SignalAgent
        from app.agents.risk_agent import RiskAgent
        from app.agents.execution_agent import ExecutionAgent

        self.agents: dict[str, BaseAgent] = {
            "whale": WhaleAgent(),
            "signal": SignalAgent(),
            "risk": RiskAgent(),
            "execution": ExecutionAgent(),
        }

        # Heavy agents skipped on low-memory production tiers
        if settings.APP_ENV != "production":
            from app.agents.research_agent import ResearchAgent
            from app.agents.monitoring_agent import MonitoringAgent
            self.agents["research"] = ResearchAgent()
            self.agents["monitoring"] = MonitoringAgent()

    async def start_all(self):
        logger.info("orchestrator_starting", agent_count=len(self.agents))
        await EventBus.publish("agent:event", "orchestrator.started", "orchestrator", {})

        tasks = [agent.start() for agent in self.agents.values()]
        await asyncio.gather(*tasks)

    async def stop_all(self):
        logger.info("orchestrator_stopping")
        await EventBus.publish("agent:event", "orchestrator.stopped", "orchestrator", {})
        for name, agent in self.agents.items():
            await agent.stop()
            logger.info("agent_stopped", agent=name)

    async def get_status(self) -> dict:
        return {
            name: {"running": agent.running} for name, agent in self.agents.items()
        }


if __name__ == "__main__":
    orchestrator = Orchestrator()

    try:
        asyncio.run(orchestrator.start_all())
    except KeyboardInterrupt:
        asyncio.run(orchestrator.stop_all())
