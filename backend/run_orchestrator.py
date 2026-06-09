import asyncio
from app.agents.orchestrator import Orchestrator
from app.core.system_mode import ModeManager, set_global_manager

async def run():
    manager = ModeManager()
    await manager.load_from_redis()
    set_global_manager(manager)

    orchestrator = Orchestrator()
    try:
        await orchestrator.start_all()
    except KeyboardInterrupt:
        await orchestrator.stop_all()

if __name__ == "__main__":
    asyncio.run(run())
